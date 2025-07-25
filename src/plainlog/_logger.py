# SPDX-FileCopyrightText: 2023 Wolfgang Langner <tds333@mailbox.org>
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
import atexit
import collections.abc
import contextlib
import logging
import sys
import traceback
from contextvars import ContextVar
from copy import deepcopy
from datetime import datetime, timezone
from enum import Enum
from functools import partial
from multiprocessing import current_process
from queue import SimpleQueue
from threading import Event, Thread
from typing import Any, Callable, Dict, Generator, Iterable, Optional, Tuple, Union

from . import _env
from ._frames import get_frame
from ._recattrs import HandlerRecord, Level, Options

get_now_utc = partial(datetime.now, timezone.utc)
plainlog_context: ContextVar[dict] = ContextVar("plainlog_context")
logger_process = current_process()

# predefined for performance reason
LEVEL_DEBUG: Level = Level(logging.DEBUG, "DEBUG")
LEVEL_INFO: Level = Level(logging.INFO, "INFO")
LEVEL_WARNING: Level = Level(logging.WARNING, "WARNING")
LEVEL_ERROR: Level = Level(logging.ERROR, "ERROR")
LEVEL_CRITICAL: Level = Level(logging.CRITICAL, "CRITICAL")


class Command(str, Enum):
    LOG = "LOG"
    STOP = "STOP"
    ADD_HANDLER = "ADD_HANDLER"
    REMOVE_HANDLER = "REMOVE_HANDLER"
    OPTIONS = "OPTIONS"
    UPDATE_LEVELS = "UPDATE_LEVELS"
    EVENT = "EVENT"


LevelInput = Union[int, str, Level]
Levels = Dict[LevelInput, Level]
Callables = Union[Callable, Iterable[Callable]]


def _validate_callables(
    callables: Optional[Union[Callable, Iterable[Callable]]], name: str = "Callable"
) -> Tuple[Callable, ...]:
    if callables is not None:
        if isinstance(callables, collections.abc.Iterable):
            callables = tuple(callables)
        else:
            callables = (callables,)

        for c in callables:
            if not callable(c):
                raise ValueError(f"{name} '{c}' must be a callable object.")
    else:
        callables = ()

    return callables


def _validate_extra(extra: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if extra is None:
        extra = {}
    else:
        if not isinstance(extra, collections.abc.Mapping):
            raise ValueError("Extra must be a Mapping (dict like) object.")
        extra = deepcopy(extra)

    return extra


def _validate_name(name: str) -> str:
    if not isinstance(name, str):
        raise ValueError("Name must be a string.")

    return name


def _get_levels() -> Levels:
    levels: Levels = {}
    for no, name in logging._levelToName.items():
        level = Level(no, name)
        levels[no] = level
        levels[name] = level
        levels[level] = level
        levels[name[0]] = level

    return levels


class Core:
    def __init__(self) -> None:
        self._min_level_no: int = sys.maxsize
        self._levels: Levels = _get_levels()
        self._handlers: Dict[str, HandlerRecord] = {}
        self._options: Options = Options("CORE", (), (), {})
        self._queue: SimpleQueue = SimpleQueue()
        self._thread: Thread = Thread(target=self._worker, daemon=True, name="plainlog-worker")
        self._thread.start()

    def __repr__(self) -> str:
        handlers = list(self._handlers.values())
        return f"<plainlog.Core handlers={handlers!r}>"

    @property
    def options(self) -> Options:
        return self._options

    @property
    def min_level_no(self) -> int:
        return self._min_level_no

    def _put(self, command: Command, message: Any = None) -> None:
        self._queue.put((command, message))

    def log(self, log_record: Dict[str, Any], processors: Callables) -> None:
        self._queue.put((Command.LOG, (log_record, processors)))

    def stop(self) -> None:
        self._put(Command.STOP)

    def join(self) -> None:
        self._thread.join()

    def is_alive(self) -> bool:
        return self._thread.is_alive()

    def level(self, level: Union[str, int, Level]) -> Level:
        ret = self._levels.get(level)

        if ret is None:
            raise ValueError(f"Invalid level {level!r}. Does not exist.")

        return ret

    def configure(
        self,
        *,
        handlers=None,
        extra: Optional[Dict[str, Any]] = None,
        preprocessors: Optional[Callables] = None,
        processors: Optional[Callables] = None,
        update_levels: bool = False,
    ) -> list:
        if handlers is not None:
            self.remove()
        else:
            handlers = []

        if update_levels:
            self._put(Command.UPDATE_LEVELS)

        extra = _validate_extra(extra)
        preprocessors = _validate_callables(preprocessors, "Preprocessor")
        processors = _validate_callables(processors, "Processor")
        options = Options("CORE", preprocessors, processors, extra)
        self._put(Command.OPTIONS, options)

        added = []
        for params in handlers:
            added.append(self.add(**params))
        if not added:
            self.wait_for_processed(_env.DEFAULT_WAIT_TIMEOUT)

        return added

    def wait_for_processed(self, timeout: Optional[float] = None) -> None:
        event: Event = Event()
        self._put(Command.EVENT, event)
        event.wait(timeout)

    def add(
        self,
        handler: Callable,
        name: Optional[str] = None,
        level: Optional[Union[str, int, Level]] = None,
        print_errors: bool = True,
    ) -> HandlerRecord:
        if not callable(handler):
            raise TypeError("Cannot log to objects of type '%s'. Object must be a callable." % type(handler).__name__)

        if name is None:
            try:
                name = handler.__name__  # type: ignore
            except AttributeError:
                name = handler.__class__.__name__

        level = _env.PLAINLOG_LEVEL if level is None else level
        level = self.level(level)

        handler_record: HandlerRecord = HandlerRecord(name, level, print_errors, handler)

        self._put(Command.ADD_HANDLER, handler_record)
        self.wait_for_processed(_env.DEFAULT_WAIT_TIMEOUT)

        return handler_record

    def remove(self, name: Optional[str] = None) -> None:
        if not (name is None or isinstance(name, str)):
            raise TypeError("Invalid handler name, it should be an string or None, not: '%s'" % type(name))

        self._put(Command.REMOVE_HANDLER, name)
        self.wait_for_processed(_env.DEFAULT_WAIT_TIMEOUT)

    def has_handlers(self) -> bool:
        return bool(self._handlers)

    def close(self) -> None:
        if self.is_alive():
            self.wait_for_processed(_env.DEFAULT_WAIT_TIMEOUT)
            self.remove()
            self.stop()
            self.join()

    def _worker(self) -> None:
        queue = self._queue

        while True:
            # command, message = None, None
            # with contextlib.suppress(Exception):
            try:
                command, message = queue.get()
            except Exception:
                continue

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
                if name not in self._handlers:
                    handlers[name] = handler_record
                    self._min_level_no = min(self._min_level_no, handler_record.level.no)
                    self._handlers = handlers

            elif command is Command.REMOVE_HANDLER:
                handlers = self._handlers.copy()
                name_ = message
                handler_names = list(handlers.keys())
                if name_ is not None:
                    handler_names = [name_]

                for handler_name in handler_names:
                    if handler_name not in handlers:
                        continue
                    else:
                        name, level, print_errors, handler = handlers.pop(handler_name)

                    levelnos = (h.level.no for h in handlers.values())
                    self._min_level_no = min(levelnos, default=sys.maxsize)

                    if hasattr(handler, "close") and callable(handler.close):  # type: ignore
                        try:
                            handler.close()
                        except Exception as ex:
                            if print_errors:
                                print(
                                    f"Error in handler.close(). Handler: {name!r} Error: {ex!r}",
                                    file=sys.stderr,
                                )
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
    def _print_error(record: dict, handler_name: str, exception=None) -> None:
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
    __slots__ = ("_core", "_options")

    # core should be the same for every logger, options change per logger
    def __init__(
        self,
        core: Core,
        name: str,
        preprocessors: Optional[Callables],
        processors: Optional[Callables],
        extra: Optional[Dict[str, Any]],
    ):
        self._core = core
        name = _validate_name(name)
        preprocessors = _validate_callables(preprocessors, "Preprocessor")
        processors = _validate_callables(processors, "Processor")
        extra = _validate_extra(extra)
        self._options = Options(name, preprocessors, processors, extra)

    def __repr__(self) -> str:
        name = self._options.name
        core = repr(self._core)
        return f"<plainlog.Logger name={name!r} core={core}>"

    def new(self, name: Optional[str] = None, preprocessors=None, processors=None, extra=None):
        name_, preprocessors_, processors_, extra_ = self._options
        # special handling to autodetect name, only for empty new
        if name is None and preprocessors is None and processors is None and extra is None:
            names = []
            frame = get_frame(1)
            with contextlib.suppress(KeyError):
                module_name = frame.f_globals["__name__"]
                names.append(module_name)
                code = frame.f_code
                qualname = code.co_name
                # file_name = code.co_filename
                with contextlib.suppress(AttributeError):
                    qualname = code.co_qualname  # from 3.11 on available
                if qualname and qualname != "<module>":
                    names.append(qualname)
            name = ".".join(names)  # TODO: finish impl to handle all cases and asign names correct

        name = name_ if name is None else name
        preprocessors = preprocessors_ if preprocessors is None else preprocessors
        processors = processors_ if processors is None else processors
        extra = extra_ if extra is None else extra

        return self.__class__(self._core, name, preprocessors, processors, extra)

    def __getstate__(self) -> object:
        return self._options

    def __setstate__(self, state) -> None:
        global logger_core
        self._options = state
        self._core = logger_core

    def bind(self, **kwargs) -> "Logger":
        name, preprocessors, processors, extra = self._options
        return self.__class__(self._core, name, preprocessors, processors, {**extra, **kwargs})

    def unbind(self, *args) -> "Logger":
        name, preprocessors, processors, old_extra = self._options
        extra: Dict[str, Any] = old_extra.copy()
        for key in args:
            extra.pop(key, None)

        return self.__class__(self._core, name, preprocessors, processors, extra)

    def get_core(self) -> Core:
        return self._core

    @staticmethod
    def context(**kwargs):
        new_context = {**plainlog_context.get({}), **kwargs}
        token = plainlog_context.set(new_context)

        return token

    @staticmethod
    def reset_context(token) -> None:
        plainlog_context.reset(token)

    @staticmethod
    @contextlib.contextmanager
    def contextualize(**kwargs) -> Generator:  # noqa: N805
        token = Logger.context(**kwargs)
        try:
            yield token
        finally:
            Logger.reset_context(token)

    def _log(self, level: Level, msg: str, args: Tuple[Any, ...], kwargs: dict) -> Optional[dict]:
        level_no, _ = level
        core = self._core

        if level_no < core.min_level_no:
            return None

        current_datetime = get_now_utc()

        _, core_preprocessors, __, core_extra = core.options
        name, preprocessors, processors, extra = self._options

        log_record = {
            "level": level,
            "msg": msg,  # raw message as in std logging
            "message": str(msg),
            "name": name,
            "datetime": current_datetime,
            "process_id": logger_process.ident,
            "process_name": logger_process.name,
            "context": {**plainlog_context.get({})},
            "extra": {**core_extra, **extra},
            "args": args,
            "kwargs": kwargs,
        }

        stop = False
        for preprocessor in (*preprocessors, *core_preprocessors):
            stop = preprocessor(log_record)
            if stop:
                return None

        core.log(log_record, processors)

        return log_record

    def debug(self, msg: str, *args, **kwargs) -> None:  # noqa: N805
        self._log(LEVEL_DEBUG, msg, args, kwargs)

    def info(self, msg: str, *args, **kwargs) -> None:  # noqa: N805
        self._log(LEVEL_INFO, msg, args, kwargs)

    def warning(self, msg: str, *args, **kwargs) -> None:  # noqa: N805
        self._log(LEVEL_WARNING, msg, args, kwargs)

    def error(self, msg: str, *args, **kwargs) -> None:  # noqa: N805
        self._log(LEVEL_ERROR, msg, args, kwargs)

    def critical(self, msg: str, *args, **kwargs) -> None:  # noqa: N805
        self._log(LEVEL_CRITICAL, msg, args, kwargs)

    def exception(self, msg: str, *args, **kwargs) -> None:  # noqa: N805
        kwargs["exc_info"] = True
        self._log(LEVEL_ERROR, msg, args, kwargs)

    def log(self, level: LevelInput, msg: str, *args, **kwargs) -> None:
        level = self._core.level(level)
        self._log(level, msg, args, kwargs)

    def __call__(self, level: LevelInput = LEVEL_DEBUG, msg="", *args, **kwargs) -> Optional[dict]:
        level = self._core.level(level)
        return self._log(level, msg, args, kwargs)


logger_core: Core = Core()
atexit.register(logger_core.close)

logger: Logger = Logger(
    core=logger_core,
    name="root",
    preprocessors=None,
    processors=None,
    extra={},
)
