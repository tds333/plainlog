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
from copy import copy
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
from ._base import HandlerProtocol, Level, Msg, Record, RecordException
from ._frames import get_frame

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
        # ret = deepcopy(extra)
        ret = copy(extra)

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
                        # record: Record = copy(log_record)
                        record: Record = log_record
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
    """Logger that sends structured log records to a shared Core.

    Each Logger is tied to a single Core instance, a ``name``, and an
    ``extra`` dict of static key-value pairs that are attached to every
    record.

    Use :meth:`bind` / :meth:`unbind` to derive a new logger with
    additional or fewer extra keys.  Use :meth:`new` to create a child
    logger (optionally with an auto-detected name).

    Attributes:
        name: Logger name (e.g. ``"root"``, ``"mymodule.MyClass"``).
        extra: Read-only copy of the static extra key-value pairs.
        core: The shared Core this logger writes to.
    """

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
        # return deepcopy(self._extra)
        return copy(self._extra)

    def new(
        self,
        name: Optional[str] = None,
        extra=None,
    ):
        """Create a child logger, optionally auto-detecting the caller name.

        Args:
            name: Explicit logger name. When ``None`` the name is
                auto-detected from the caller's frame (module + qualname).
            extra: Extra key-value pairs. Falls back to the parent's
                ``extra`` when ``None``.

        Returns:
            A new Logger instance.
        """
        # special handling to autodetect name
        if name is None:
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
        """Return a new logger with additional extra keys.

        Args:
            **kwargs: Key-value pairs to merge into the logger's extra dict.

        Returns:
            A new Logger with the combined extra dict.
        """
        return self.__class__(
            self._core,
            self._name,
            {**self._extra, **kwargs},
        )

    def unbind(self, *args) -> "Logger":
        """Return a new logger with the given extra keys removed.

        Args:
            *args: Extra keys to remove.

        Returns:
            A new Logger without the specified extra keys.
        """
        extra: Dict[str, Any] = self._extra.copy()
        for key in args:
            extra.pop(key, None)

        return self.__class__(self._core, self._name, extra)

    @staticmethod
    def context(**kwargs):
        """Set context variables for the current execution context.

        Args:
            **kwargs: Key-value pairs to merge into the context.

        Returns:
            A ``Token`` that can be passed to :meth:`reset_context`.
        """
        new_context = {**plainlog_context.get({}), **kwargs}
        token = plainlog_context.set(new_context)

        return token

    @staticmethod
    def reset_context(token) -> None:
        """Reset the ContextVar to its previous value.

        Args:
            token: The token returned by :meth:`context`.
        """
        plainlog_context.reset(token)

    @staticmethod
    @contextlib.contextmanager
    def contextualize(**kwargs) -> Generator:  # noqa: N805
        """Context manager that sets kwargs as context variables.

        Args:
            **kwargs: Key-value pairs to set as context variables.

        Yields:
            The token returned by :meth:`context`.

        Example:
            with logger.contextualize(request_id="abc"):
                logger.info("handling request")
        """
        token = Logger.context(**kwargs)
        try:
            yield token
        finally:
            Logger.reset_context(token)

    def _log(self, level: Level, msg: Msg, kwargs: dict) -> Record:
        core = self._core

        if core._handler is None or core.min_level_no > level[0]:
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
        """Log *msg* at DEBUG level."""
        self._log(LEVEL_DEBUG, msg, kwargs)

    def info(self, msg: Msg, **kwargs) -> None:  # noqa: N805
        """Log *msg* at INFO level."""
        self._log(LEVEL_INFO, msg, kwargs)

    def warning(self, msg: Msg, **kwargs) -> None:  # noqa: N805
        """Log *msg* at WARNING level."""
        self._log(LEVEL_WARNING, msg, kwargs)

    def error(self, msg: Msg, **kwargs) -> None:  # noqa: N805
        """Log *msg* at ERROR level."""
        self._log(LEVEL_ERROR, msg, kwargs)

    def critical(self, msg: Msg, **kwargs) -> None:  # noqa: N805
        """Log *msg* at CRITICAL level."""
        self._log(LEVEL_CRITICAL, msg, kwargs)

    def exception(self, msg: Msg, **kwargs) -> None:  # noqa: N805
        """Log msg at ERROR level and attach exception info.

        If ``exc_info`` is not already set it defaults to ``True``.

        Args:
            msg: The message to log.
            **kwargs: Additional record fields.
        """
        kwargs["exc_info"] = kwargs.get("exc_info", True)
        self._log(LEVEL_ERROR, msg, kwargs)

    def log(self, level: LevelInput, msg: Msg, **kwargs) -> None:
        """Log msg at the given level.

        Args:
            level: Log level as int, str, or Level named tuple.
            msg: The message to log.
            **kwargs: Additional record fields.
        """
        level = self._core.level(level)
        self._log(level, msg, kwargs)

    def configure(
        self,
        *,
        handler: Optional[HandlerProtocol] = None,
        level: Optional[Union[str, int, Level]] = None,
        print_errors: Optional[bool] = None,
    ) -> None:
        """Configure the shared Core handler, level, and error printing.

        Shortcut for :meth:`Core.configure`.

        Args:
            handler: Handler to install, or ``None`` to remove.
            level: Minimum log level.
            print_errors: Print handler errors to stderr.
        """
        self._core.configure(handler=handler, level=level, print_errors=print_errors)

    def __call__(
        self, level: LevelInput = LEVEL_DEBUG, msg: Msg = "", **kwargs
    ) -> Record:
        """Callable interface: logger(level, msg, **kwargs).

        Args:
            level: Log level as int, str, or Level. Defaults to DEBUG.
            msg: The message to log. Defaults to ``""``.
            **kwargs: Additional record fields.

        Returns:
            The created Record dict, or ``{}`` if filtered out.
        """
        level = self._core.level(level)
        return self._log(level, msg, kwargs)


logger_core: Core = Core()

atexit.register(logger_core.close)

logger: Logger = Logger(
    core=logger_core,
    name="root",
    extra={},
)
"""Module-level Logger convenience instance.

Usage::

    from plainlog import logger

    logger.info("hello world")
"""
