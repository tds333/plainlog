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
from copy import copy, deepcopy
from datetime import datetime, timezone
from enum import Enum
from functools import partial
from multiprocessing import current_process
from queue import SimpleQueue
from threading import Event, Thread
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    Iterable,
    Optional,
    Union,
)

from . import _env
from ._frames import get_frame
from ._recattrs import HandlerProtocol, Level, Msg, Record, RecordException

get_now_utc = partial(datetime.now, timezone.utc)
plainlog_context: ContextVar[dict] = ContextVar("plainlog_context")
logger_process = current_process()

# predefined for performance reason
LEVEL_NOTSET: Level = Level(logging.NOTSET, "NOTSET")
LEVEL_DEBUG: Level = Level(logging.DEBUG, "DEBUG")
LEVEL_INFO: Level = Level(logging.INFO, "INFO")
LEVEL_WARNING: Level = Level(logging.WARNING, "WARNING")
LEVEL_ERROR: Level = Level(logging.ERROR, "ERROR")
LEVEL_CRITICAL: Level = Level(logging.CRITICAL, "CRITICAL")


class Command(str, Enum):
    LOG = "LOG"
    STOP = "STOP"
    CONFIGURE = "CONFIGURE"
    EVENT = "EVENT"


LevelInput = Union[int, str, Level]
Levels = Dict[LevelInput, Level]
Callables = Union[Callable, Iterable[Callable]]


def _validate_extra(extra: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    ret: Dict[str, Any] = {}
    if extra is not None:
        if not isinstance(extra, collections.abc.Mapping):
            raise ValueError("Extra must be a Mapping (dict like) object.")
        ret = deepcopy(extra)

    return ret


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


def _validate_level(level) -> Level:
    levels = _get_levels()
    try:
        ret = levels[level]
    except Exception as e:
        raise ValueError(f"Invalid log level {level}") from e

    return ret


class Core:
    def __init__(self, name: Optional[str] = None) -> None:
        self._name: str = "CORE" if name is None else _validate_name(name)
        self._min_level_no: int = logging.NOTSET
        self._levels: Levels = _get_levels()
        self._handler: Optional[HandlerProtocol] = None
        # self._extra: dict = {}
        self._print_errors = False
        self._queue: SimpleQueue = SimpleQueue()
        self._thread: Thread = Thread(
            target=self._worker, daemon=True, name="plainlog-worker"
        )
        self._thread.start()

    def __repr__(self) -> str:
        name = self.name
        return f"<plainlog.Core({name=})>"

    @property
    def name(self) -> str:
        return self._name

    @property
    def handler(self) -> Optional[HandlerProtocol]:
        return self._handler

    @property
    def min_level_no(self) -> int:
        return self._min_level_no

    def _put(self, command: Command, message: Any = None) -> None:
        self._queue.put((command, message))

    def log(self, log_record: Record) -> Record:
        if self._handler is not None:
            try:
                log_record = self._handler.preprocess(log_record)
                if not log_record:  # Stop processing if Handler decides so
                    return log_record
            except Exception as ex:
                if self._print_errors:
                    print(
                        f"Error in handler.preprocess() for handler {self._handler!r}. Error: {ex!r}",
                        file=sys.stderr,
                    )
            self._queue.put((Command.LOG, log_record))

            return log_record

        return {}

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
        handler: Union[HandlerProtocol, None],
        level: Optional[Union[str, int, Level]] = None,
        print_errors=None,
    ) -> None:
        if level is not None:
            level = _validate_level(level)

        self._put(Command.CONFIGURE, (handler, level, print_errors))

        self.wait_for_processed(_env.DEFAULT_WAIT_TIMEOUT)

    def wait_for_processed(self, timeout: Optional[float] = None) -> None:
        event: Event = Event()
        self._put(Command.EVENT, event)
        event.wait(timeout)

    def close(self) -> None:
        if self.is_alive():
            self.configure(level=None, handler=None, print_errors=False)
            self.stop()
            self.join()

    def _worker(self) -> None:
        queue_get = self._queue.get
        self_handler = self._handler

        while True:
            try:
                value = queue_get()
            except Exception:
                continue

            match value:
                case (Command.LOG, log_record):
                    if self_handler is not None:
                        record: Record = copy(log_record)
                        try:
                            self_handler.process(record)
                        except Exception as ex:
                            if self._print_errors:
                                self._print_error(log_record, self_handler, ex)

                case (
                    Command.CONFIGURE,
                    (handler, level, print_errors),
                ):
                    if level is not None:
                        self._levels = _get_levels()
                        self._min_level_no = self.level(level).no
                    if print_errors is not None:
                        self._print_errors = bool(print_errors)
                    if self_handler is not None:
                        if hasattr(self_handler, "close") and callable(
                            self_handler.close
                        ):
                            try:
                                self_handler.close()
                                self._handler = self_handler = None
                            except Exception as ex:
                                if self._print_errors:
                                    print(
                                        f"Error in handler.close() for handler {self_handler.__class__.__name__!r}. Error: {ex!r}",
                                        file=sys.stderr,
                                    )
                    if handler is not None:
                        self._handler = self_handler = handler

                case (Command.STOP, _):
                    break

                case (Command.EVENT, event):
                    event.set()

    @staticmethod
    def _print_error(record: dict, handler, exception=None) -> None:
        if not sys.stderr or sys.stderr.closed:
            return

        if exception is None:
            type_, value, traceback_ = sys.exc_info()
        else:
            type_, value, traceback_ = (
                type(exception),
                exception,
                exception.__traceback__,
            )

        try:
            sys.stderr.write("--- Logging error in Plainlog handler %r ---\n" % handler)
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
    __slots__ = ("_core", "_name", "_extra")

    # core should be the same for every logger
    def __init__(
        self,
        core: Core,
        name: str,
        extra: Optional[Dict[str, Any]],
    ):
        self._core = core
        self._name = _validate_name(name)
        self._extra = _validate_extra(extra)

    def __repr__(self) -> str:
        name = self._name
        core = repr(self._core)
        return f"<plainlog.Logger name={name!r} core={core}>"

    @property
    def name(self) -> str:
        return self._name

    @property
    def extra(self) -> dict:
        return deepcopy(self._extra)

    @property
    def core(self) -> Core:
        return self._core

    def new(
        self,
        name: Optional[str] = None,
        extra=None,
    ):
        # special handling to autodetect name, only for empty new
        if name is None and extra is None:
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
            name = ".".join(
                names
            )  # TODO: finish impl to handle all cases and asign names correct

        name = self._name if name is None else name
        extra = self._extra if extra is None else extra

        return self.__class__(self._core, name, extra)

    def __getstate__(self) -> object:
        return self._name, self._extra

    def __setstate__(self, state) -> None:
        global logger_core
        self._name, self._extra = state
        self._core = logger_core

    def bind(self, **kwargs) -> "Logger":
        return self.__class__(
            self._core,
            self._name,
            {**self._extra, **kwargs},
        )

    def unbind(self, *args) -> "Logger":
        extra: Dict[str, Any] = self._extra.copy()
        for key in args:
            extra.pop(key, None)

        return self.__class__(self._core, self._name, extra)

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

    def _log(self, level: Level, msg: Msg, kwargs: dict) -> Record:
        core = self._core

        if core.min_level_no > level.no or core._handler is None:
            return {}

        current_datetime = get_now_utc()
        exc_info = kwargs.pop("exc_info", False)

        log_record: Record = {
            "level": level,
            "msg": msg,  # raw message as in std logging
            "message": str(msg),
            "name": self._name,
            "datetime": current_datetime,
            "process_id": logger_process.ident,
            "process_name": logger_process.name,
            "context": {**plainlog_context.get({})},
            # "extra": {**core._extra, **self._extra},
            "extra": {**self._extra},
            "kwargs": kwargs,
        }

        if exc_info:
            type_, value, traceback = sys.exc_info()
            exception = RecordException(type_, value, traceback)
            log_record["exc_info"] = (type_, value, traceback)
            log_record["exception"] = exception

        log_record = core.log(log_record)

        return log_record

    def debug(self, msg: Msg, **kwargs) -> None:  # noqa: N805
        self._log(LEVEL_DEBUG, msg, kwargs)

    def info(self, msg: Msg, **kwargs) -> None:  # noqa: N805
        self._log(LEVEL_INFO, msg, kwargs)

    def warning(self, msg: Msg, **kwargs) -> None:  # noqa: N805
        self._log(LEVEL_WARNING, msg, kwargs)

    def error(self, msg: Msg, **kwargs) -> None:  # noqa: N805
        self._log(LEVEL_ERROR, msg, kwargs)

    def critical(self, msg: Msg, **kwargs) -> None:  # noqa: N805
        self._log(LEVEL_CRITICAL, msg, kwargs)

    def exception(self, msg: Msg, **kwargs) -> None:  # noqa: N805
        kwargs["exc_info"] = kwargs.get("exc_info", True)
        self._log(LEVEL_ERROR, msg, kwargs)

    def log(self, level: LevelInput, msg: Msg, **kwargs) -> None:
        level = self._core.level(level)
        self._log(level, msg, kwargs)

    def __call__(
        self, level: LevelInput = LEVEL_DEBUG, msg: Msg = "", **kwargs
    ) -> Record:
        level = self._core.level(level)
        return self._log(level, msg, kwargs)


logger_core: Core = Core()
atexit.register(logger_core.close)

logger: Logger = Logger(
    core=logger_core,
    name="root",
    extra={},
)
