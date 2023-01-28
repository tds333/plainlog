# SPDX-FileCopyrightText: 2023 Wolfgang Langner <tds333@mailbox.org>
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
import contextlib
import logging
import sys
import collections.abc
from contextvars import ContextVar
from copy import deepcopy
from datetime import datetime, timezone
from threading import Thread, Event
from queue import SimpleQueue
from enum import Enum
import atexit
import traceback
from functools import partial
#from time import time_ns

from . import _defaults
from ._recattrs import RecordException, Level, HandlerRecord, Options
from ._frames import get_frame


get_now_utc = partial(datetime.now, timezone.utc)
start_time = get_now_utc()
context = ContextVar("plainlog_context", default={})

# predefined for performance reason
LEVEL_DEBUG = Level(logging.DEBUG, "DEBUG")
LEVEL_INFO = Level(logging.INFO, "INFO")
LEVEL_WARNING = Level(logging.WARNING, "WARNING")
LEVEL_ERROR = Level(logging.ERROR, "ERROR")
LEVEL_CRITICAL = Level(logging.CRITICAL, "CRITICAL")


class Command(str, Enum):
    LOG = "LOG"
    STOP = "STOP"
    ADD_HANDLER = "ADD_HANDLER"
    REMOVE_HANDLER = "REMOVE_HANDLER"
    OPTIONS = "OPTIONS"
    UPDATE_LEVELS = "UPDATE_LEVELS"
    EVENT = "EVENT"


def _validate_callables(callables, name="Callable"):
    if callables is not None:
        if isinstance(callables, collections.abc.Iterable):
            callables = tuple(callables)
        else:
            callables = (callables, )

        for c in callables:
            if not callable(c):
                raise ValueError(f"{name} '{c}' must be a callable object.")
    else:
        callables = tuple()

    return callables


def _validate_extra(extra):
    if extra is None:
        extra = {}
    else:
        if not isinstance(extra, collections.abc.Mapping):
            raise ValueError("Extra must be a Mapping (dict like) object.")
        extra = deepcopy(extra)
    
    return extra


def _validate_name(name):
    if not isinstance(name, str):
        raise ValueError("Name must be a string.")

    return name


def _get_levels():
    levels = {}
    for no, name in logging._levelToName.items():
        level = Level(no, name)
        levels[no] = level
        levels[name] = level
        levels[level] = level
        levels[name[0]] = level
    
    return levels


class Core:
    def __init__(self):
        self._max_level_no = sys.maxsize
        self.min_level_no = self._max_level_no
        self._levels = _get_levels()
        self._handlers = {}
        self._options = Options("CORE", tuple(), tuple(), {})
        self._queue = SimpleQueue()
        self._thread = Thread(target=self._worker, daemon=True, name="plainlog-worker")
        self._thread.start()

    def __getstate__(self):
        state = self.__dict__.copy()
        state["_queue"] = None
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._queue = SimpleQueue()
    
    def __repr__(self):
        handlers = list(self._handlers.values())
        return f"<plainlog.Core handlers={handlers!r}>"
    
    def put(self, message, command=Command.LOG):
        self._queue.put((command, message))

    def stop(self):
        self.put(None, Command.STOP)
    
    def join(self):
        self._thread.join()
    
    def is_alive(self):
        return self._thread.is_alive()
    
    def level(self, level):
        ret = self._levels.get(level)

        if ret is None:
            raise ValueError(f"Invalid level {level!r}. Does not exist.")

        return ret
    
    def configure(self, *, handlers=None, extra=None, preprocessors=None, processors=None, update_levels=False):
        if handlers is not None:
            self.remove()
        else:
            handlers = []
        
        if update_levels:
            self.put((None, Command.UPDATE_LEVELS))
        
        extra = _validate_extra(extra)
        preprocessors = _validate_callables(preprocessors, "Preprocessor")
        processors = _validate_callables(processors, "Processor")
        options = Options("CORE", preprocessors, processors, extra)
        self.put(options, Command.OPTIONS)

        return [self.add(**params) for params in handlers]
    
    def wait_for_processed(self, timeout=None):
        event = Event()
        self.put(event, Command.EVENT)
        event.wait(timeout)

    def add(
        self,
        handler,
        name = None,
        level=None,
        print_errors=True,
    ):

        if not callable(handler):
            raise TypeError("Cannot log to objects of type '%s'. Object must be a callable." % type(handler).__name__)

        if name is None:
            try:
                name = handler.__name__
            except AttributeError:
                name = handler.__class__.__name__

        level = _defaults.PLAINLOG_LEVEL if level is None else level
        level = self.level(level)

        handler_record = HandlerRecord(name, level, print_errors, handler)

        self.put(handler_record, Command.ADD_HANDLER)
        self.wait_for_processed()

        return handler_record

    def remove(self, name=None):
        if not (name is None or isinstance(name, str)):
            raise TypeError(
                "Invalid handler name, it should be an string "
                "or None, not: '%s'" % type(handler_id).__name__
            )

        self.put(name, Command.REMOVE_HANDLER)
        self.wait_for_processed()
    
    def close(self):
        if self.is_alive():
            self.remove()
            self.stop()
            self.join()
    
    def _worker(self):
        queue = self._queue

        while True:
            command, message = None, None
            with contextlib.suppress(Exception):
                command, message = queue.get()
                len_handlers = len(self._handlers)

            if command is Command.LOG:
                log_record, processors = message

                stop = False
                for p in (*processors, *self._options.processors):
                    with contextlib.suppress(Exception):
                        stop = p(log_record)
                    if stop:
                        break  # for loop

                if stop:
                    continue  # with while loop to process next commands
                
                for name, level, print_errors, handler in self._handlers.values():
                    if log_record["level"].no >= level.no:
                        try:
                            handler(log_record.copy())
                        except Exception as ex:
                            if print_errors:
                                self._print_error(log_record, name, ex)

            elif command is Command.STOP:
                break

            elif command is Command.ADD_HANDLER:
                handlers = self._handlers.copy()
                handler_record = message
                name = handler_record.name
                if not name in self._handlers:
                    handlers[name] = handler_record
                    self.min_level_no = min(self.min_level_no, handler_record.level.no)
                    self._handlers = handlers

            elif command is Command.REMOVE_HANDLER:
                handlers = self._handlers.copy()
                name_ = message
                handler_names = list(handlers.keys())
                if name_ is not None:
                    handler_names = [name_]

                for handler_name in handler_names:
                    name, level, print_errors, handler = handlers.pop(handler_name, (None, None, None, None))

                    if name is None:
                        continue

                    levelnos = (h.level.no for h in handlers.values())
                    self.min_level_no = min(levelnos, default=self._max_level_no)
                    #self._handlers = handlers

                    if hasattr(handler, "close") and callable(handler.close):
                        try:
                            handler.close()
                        except Exception as ex:
                            if print_errors:
                                print(f"Error in handler.close(). Handler: {name!r} Error: {ex!r}", file=sys.stderr)
                self._handlers = handlers
            
            elif command is Command.OPTIONS:
                options = message
                self._options = options
            
            elif command is Command.UPDATE_LEVELS:
                self._levels = _get_levels()

            elif command is Command.EVENT:
                event = message
                event.set()

    @staticmethod
    def _print_error(record, handler_name, exception=None):
        if not sys.stderr or sys.stderr.closed:
            return

        if exception is None:
            type_, value, traceback_ = sys.exc_info()
        else:
            type_, value, traceback_ = (type(exception), exception, exception.__traceback__)

        try:
            sys.stderr.write("--- Logging error in Plainlog Handler %r ---\n" % handler_name)
            try:
                record_repr = str(record)
            except Exception:
                record_repr = "/!\\ Unprintable record /!\\"
            sys.stderr.write("Record was: %s\n" % record_repr)
            traceback.print_exception(type_, value, traceback_, None, sys.stderr)
            sys.stderr.write("--- End of logging error ---\n")
        except OSError:
            pass
        finally:
            del type_, value, traceback_


class Logger:

    # core should be the same for every logger, options change per logger
    def __init__(self, core, name, preprocessors, processors, extra):
        self._core = core
        name = _validate_name(name)
        preprocessors = _validate_callables(preprocessors, "Preprocessor")
        processors = _validate_callables(processors, "Processor")
        extra = _validate_extra(extra)
        self._options = Options(name, preprocessors, processors, extra)

    def __repr__(self):
        name = self._options.name
        core = repr(self._core)
        return f"<plainlog.Logger name={name!r} core={core}>"

    def bind(self, **kwargs):  # noqa: N805
        *options, extra = self._options
        return Logger(self._core, *options, {**extra, **kwargs})
    
    def unbind(self, *args):  # noqa: N805
        *options, old_extra = self._options
        extra = old_extra.copy()
        for key in args:
            extra.pop(key, None)

        return Logger(self._core, *options, extra)

    @contextlib.contextmanager
    def contextualize(__self, **kwargs):  # noqa: N805
        global context
        new_context = {**context.get(), **kwargs}
        token = context.set(new_context)
        try:
            yield
        finally:
            context.reset(token)
   
    def bind_context(__self, **kwargs):
        global context
        new_context = {**context.get(), **kwargs}
        token = context.set(new_context)

        return token
    
    def unbind_context(__self, *args):
        global context
        #context_dict = context.get().copy()
        context_dict = {**context.get()}
        for key in args:
            context_dict.pop(key, None)
        token = context.set(context_dict)

        return token

    def context(__self, **kwargs):
        global context
        new_context = {**kwargs}
        token = context.set(new_context)

        return token
    
    def reset_context(__self, token):
        global context
        context.reset(token)

    def level(self, level):
        return self._core.level(level)
    
    def name(self, name=None):
        if name is None:
            name = "root"
            frame = get_frame(2)
            try:
                name = frame.f_globals["__name__"]
            except KeyError:
                name = None

        if not isinstance(name, str):
            raise ValueError("Name must be a string.")
        options = self._options._replace(name=name)
        return Logger(self._core, *options)

    def preprocessor(self, *args):
        options = self._options._replace(preprocessors=args)
        return Logger(self._core, *options)
    
    def processor(self, *args):
        options = self._options._replace(processors=args)
        return Logger(self._core, *options)
    
    def extra(self, **kwargs):
        options = self._options._replace(extra=kwargs)
        return Logger(self._core, *options)

    def _log(self, level, msg, args, kwargs):
        level_no, _ = level
        core = self._core
        
        if level_no < core.min_level_no:
            return
        
        current_datetime = get_now_utc()
        elapsed = current_datetime - start_time

        _, core_preprocessors, __, core_extra = core._options
        name, preprocessors, processors, extra = self._options

        log_record = {
            "elapsed": elapsed,
            "level": level,
            "msg": msg,  # raw message as in std logging
            "message": str(msg),
            "name": name,
            "datetime": current_datetime,
            #"time_ns": time_ns(),
            "context": {**context.get()},
            "extra": {**core_extra, **extra},
            "args": args,
            "kwargs": kwargs,
        }

        stop = False
        for preprocessor in (*preprocessors, *core_preprocessors):
            #with contextlib.suppress(Exception):
            stop = preprocessor(log_record)
            if stop:
                return

        core.put((log_record, processors))

    def debug(self, msg, *args, **kwargs):  # noqa: N805
        self._log(LEVEL_DEBUG, msg, args, kwargs)

    def info(self, msg, *args, **kwargs):  # noqa: N805
        self._log(LEVEL_INFO, msg, args, kwargs)

    def warning(self, msg, *args, **kwargs):  # noqa: N805
        self._log(LEVEL_WARNING, msg, args, kwargs)

    def error(self, msg, *args, **kwargs):  # noqa: N805
        self._log(LEVEL_ERROR, msg, args, kwargs)

    def critical(self, msg, *args, **kwargs):  # noqa: N805
        self._log(LEVEL_CRITICAL, msg, args, kwargs)

    def exception(self, msg, *args, **kwargs):  # noqa: N805
        kwargs["exc_info"] = True
        self._log(LEVEL_ERROR, msg, args, kwargs)

    def log(self, level, msg, *args, **kwargs):  # noqa: N805
        level = self.level(level)
        self._log(level, msg, args, kwargs)

    def __call__ (self, level=LEVEL_DEBUG, msg="", *args, **kwargs):  # noqa: N805
        level = self.level(level)
        self._log(level, msg, args, kwargs)


logger_core = Core()
atexit.register(logger_core.close)
#logger = Logger(core=logger_core, name="root", preprocessors=None, processors=None, extra={})
