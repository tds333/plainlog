# SPDX-FileCopyrightText: 2023 Wolfgang Langner <tds333@mailbox.org>
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
import atexit
import collections.abc
import contextlib
import logging
import os
import sys
import traceback
from contextvars import ContextVar
from copy import copy
from enum import Enum
from multiprocessing import current_process
from queue import SimpleQueue
from threading import Event, Thread, current_thread
from time import time
from typing import (
    Any,
    Dict,
    Generator,
    Iterable,
    Optional,
    Union,
)

from . import _env
from ._base import (
    Msg,
    Record,
    RecordException,
    UniversalProcessorProtocol,
)
from ._frames import add_caller_info, get_frame
from ._utils import handle_close

plainlog_context: ContextVar[dict] = ContextVar("plainlog_context")
logger_process = current_process()
logger_process_ident = logger_process.ident
logger_process_name = logger_process.name

# predefined for performance reason
LEVEL_NOTSET: int = logging.NOTSET
LEVEL_DEBUG: int = logging.DEBUG
LEVEL_INFO: int = logging.INFO
LEVEL_WARNING: int = logging.WARNING
LEVEL_ERROR: int = logging.ERROR
LEVEL_CRITICAL: int = logging.CRITICAL

start_time = time()


class Command(str, Enum):
    LOG = "LOG"
    STOP = "STOP"
    CONFIGURE = "CONFIGURE"
    EVENT = "EVENT"


def _validate_extra(extra: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    ret: Dict[str, Any] = {}
    if extra is not None:
        if not isinstance(extra, collections.abc.Mapping):
            raise ValueError("Extra must be a Mapping (dict like) object.")
        ret = copy(extra)

    return ret


def _validate_name(name: str) -> str:
    if not isinstance(name, str):
        raise ValueError("Name must be a string.")

    return name


def _safe_str(obj: Any) -> str:
    try:
        return str(obj)
    except Exception:
        return "<unprintable>"


def _safe_repr(obj: Any) -> str:
    try:
        return repr(obj)
    except Exception:
        return "<unprintable>"


_validate_level = getattr(logging, "_checkLevel")  # noqa: B009
get_level_name = logging.getLevelName

# precomputed for the logging hot path
_EMPTY_CONTEXT: dict = {}
_LEVEL_NAMES: Dict[int, str] = {
    LEVEL_NOTSET: "NOTSET",
    LEVEL_DEBUG: "DEBUG",
    LEVEL_INFO: "INFO",
    LEVEL_WARNING: "WARNING",
    LEVEL_ERROR: "ERROR",
    LEVEL_CRITICAL: "CRITICAL",
}
_CMD_LOG = Command.LOG


class Core:
    def __init__(self, name: Optional[str] = None) -> None:
        self._name: str = "CORE" if name is None else _validate_name(name)
        self._min_level_no: int = logging.NOTSET
        self._processors: tuple[UniversalProcessorProtocol, ...] = ()
        self._start_worker()

    def __repr__(self) -> str:
        name = self.name
        return f"<plainlog.Core({name=})>"

    @property
    def name(self) -> str:
        return self._name

    @property
    def processors(self) -> tuple[UniversalProcessorProtocol, ...]:
        return self._processors

    @property
    def min_level_no(self) -> int:
        return self._min_level_no

    def _put(self, command: Command, message: Any = None) -> None:
        self._queue.put((command, message))

    def log(self, log_record: Record) -> None:
        self._queue.put((Command.LOG, log_record))

    def stop(self) -> None:
        self._put(Command.STOP)

    def join(self) -> None:
        self._thread.join()

    def is_alive(self) -> bool:
        return self._thread.is_alive()

    def configure(
        self,
        *,
        processors: Optional[Iterable[UniversalProcessorProtocol]],
        level: Optional[Union[str, int]] = None,
    ) -> None:
        if not self.is_alive():
            return

        if level is not None:
            level = _validate_level(level)

        self._put(Command.CONFIGURE, (processors, level))

        self.wait_for_processed(_env.DEFAULT_WAIT_TIMEOUT)

    def wait_for_processed(self, timeout: Optional[float] = None) -> None:
        if not self._thread.is_alive():
            return
        if self._thread is current_thread():
            # cannot wait for the worker from within the worker
            return

        event: Event = Event()
        self._put(Command.EVENT, event)
        event.wait(timeout if timeout is not None else _env.DEFAULT_WAIT_TIMEOUT)

    def close(self) -> None:
        if self.is_alive():
            self.configure(level=None, processors=())
            self.stop()
            self.join()

    def _start_worker(self) -> None:
        self._queue = SimpleQueue()
        self._thread = Thread(target=self._worker, daemon=True, name="plainlog-worker")
        self._thread.start()

    def _worker(self) -> None:
        queue_get = self._queue.get
        processors = tuple(self._processors)

        while True:
            try:
                value = queue_get()
                match value:
                    case (Command.LOG, log_record):
                        record: Record = log_record
                        for processor in processors:
                            try:
                                new_record = processor(record)
                            except Exception as ex:
                                record["processor_error_message"] = _safe_str(ex)
                                record["processor_error_name_repr"] = _safe_repr(
                                    processor
                                )
                                continue
                            if not new_record:
                                break
                            if isinstance(new_record, dict):
                                record = new_record

                    case (Command.CONFIGURE, (c_processors, level)):
                        if level is not None:
                            self._min_level_no = level
                        if c_processors is not None:
                            for processor in processors:
                                try:
                                    handle_close(processor)
                                except Exception:
                                    pass
                            self._processors = processors = tuple(c_processors)

                    case (Command.STOP, _):
                        break

                    case (Command.EVENT, event):  # pragma: no cover
                        event.set()
            except Exception:  # pragma: no cover - worker must never die
                continue

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

    Use `bind()` / `unbind()` to derive a new logger with
    additional or fewer extra keys.  Use `new()` to create a child
    logger (optionally with an auto-detected name).

    Attributes:
        name: Logger name (e.g. ``"root"``, ``"mymodule.MyClass"``).
        extra: Read-only copy of the static extra key-value pairs.
        core: The shared Core this logger writes to.
    """

    __slots__ = ("_core", "_name", "_extra", "_verbose")

    # core should be the same for every logger
    def __init__(
        self,
        core: Core,
        name: str,
        extra: Optional[Dict[str, Any]] = None,
        verbose: Optional[bool] = None,
    ):
        self._core = core
        self._name = _validate_name(name)
        self._extra = _validate_extra(extra)
        self._verbose = False if not verbose else True

    def __repr__(self) -> str:
        name = self._name
        core = repr(self._core)
        return f"<plainlog.Logger name={name!r} core={core}>"

    @property
    def name(self) -> str:
        return self._name

    @property
    def extra(self) -> dict:
        return copy(self._extra)

    def new(
        self,
        name: Optional[str] = None,
        extra=None,
        verbose=False,
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

        return self.__class__(self._core, name, extra, verbose)

    def __getstate__(self) -> object:
        return self._name, self._extra, self._verbose

    def __setstate__(self, state) -> None:
        global logger_core
        self._name, self._extra, self._verbose = state
        self._core = logger_core

    def bind(self, **kwargs) -> "Logger":
        """Return a new logger with additional extra keys.

        Args:
            **kwargs: Key-value pairs to merge into the logger's extra dict.

        Returns:
            A new Logger with the combined extra dict.
        """
        return self.__class__(
            self._core, self._name, {**self._extra, **kwargs}, self._verbose
        )

    def unbind(self, *args) -> "Logger":
        """Return a new logger with the given extra keys removed.

        Args:
            *args: Extra keys to remove.

        Returns:
            A new Logger without the specified extra keys.
        """
        extra: Dict[str, Any] = copy(self._extra)
        for key in args:
            extra.pop(key, None)

        return self.__class__(self._core, self._name, extra, self._verbose)

    @staticmethod
    def context(**kwargs):
        """Set context variables for the current execution context.

        Args:
            **kwargs: Key-value pairs to merge into the context.

        Returns:
            A ``Token`` that can be passed to `reset_context()`.
        """
        new_context = {**plainlog_context.get({}), **kwargs}
        token = plainlog_context.set(new_context)

        return token

    @staticmethod
    def reset_context(token) -> None:
        """Reset the ContextVar to its previous value.

        Args:
            token: The token returned by `context()`.
        """
        plainlog_context.reset(token)

    @staticmethod
    @contextlib.contextmanager
    def contextualize(**kwargs) -> Generator:  # noqa: N805
        """Context manager that sets kwargs as context variables.

        Args:
            **kwargs: Key-value pairs to set as context variables.

        Yields:
            The token returned by `context()`.

        Example:
            with logger.contextualize(request_id="abc"):
                logger.info("handling request")
        """
        token = Logger.context(**kwargs)
        try:
            yield token
        finally:
            Logger.reset_context(token)

    def _log(self, level: int, msg: Msg, kwargs: dict) -> bool:
        core = self._core

        if not core._processors or core._min_level_no > level:
            return False

        exception = None
        if kwargs and kwargs.get("exc_info", False):
            exception = RecordException(*sys.exc_info())

        ctx = plainlog_context.get(_EMPTY_CONTEXT)
        if kwargs:
            extra = {**self._extra, **ctx, **kwargs}
        elif ctx:
            extra = {**self._extra, **ctx}
        else:
            extra = self._extra.copy()

        log_record: Record = {
            "level": level,
            "level_name": _LEVEL_NAMES.get(level) or get_level_name(level),
            "msg": msg,  # raw message as in std logging
            "name": self._name,
            "created": time(),
            "process_id": logger_process_ident,
            "process_name": logger_process_name,
            "exception": exception,
            "extra": extra,
        }

        if self._verbose:
            add_caller_info(log_record, 3)

        core._queue.put((_CMD_LOG, log_record))

        return True

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

    def log(self, level: str | int, msg: Msg, **kwargs) -> None:
        """Log msg at the given level.

        Args:
            level: Log level as int or str.
            msg: The message to log.
            **kwargs: Additional record fields.
        """
        level = _validate_level(level)
        self._log(level, msg, kwargs)

    def configure(
        self,
        *,
        processors: Optional[Iterable[UniversalProcessorProtocol]] = None,
        level: Optional[Union[str, int]] = None,
        verbose: Optional[bool] = None,
    ) -> None:
        """Configure the shared Core processors, level, and error printing.

        Shortcut for `Core.configure()`.

        Args:
            processors: Processors to install, or ``None`` to leave
                unchanged. Pass an empty iterable to remove all processors.
            level: Minimum log level.
        """
        if verbose is not None:
            self._verbose = bool(verbose)
        self._core.configure(processors=processors, level=level)

    def __call__(self, level: str | int = LEVEL_DEBUG, msg: Msg = "", **kwargs) -> bool:
        """Callable interface: logger(level, msg, **kwargs).

        Args:
            level: Log level as int or str. Defaults to DEBUG.
            msg: The message to log. Defaults to ``""``.
            **kwargs: Additional record fields.

        Returns:
            True if processed False if not
        """
        level = _validate_level(level)
        return self._log(level, msg, kwargs)


logger_core: Core = Core()

atexit.register(logger_core.close)

logger: Logger = Logger(core=logger_core, name="root", extra={}, verbose=False)
"""Module-level Logger convenience instance.

Usage::

    from plainlog import logger

    logger.info("hello world")
"""


def _reset_for_fork() -> None:
    global logger_process, logger_process_ident, logger_process_name

    proc = current_process()
    logger_process = proc
    logger_process_ident = proc.ident
    logger_process_name = proc.name

    logger_core._start_worker()


def _register_fork_hook() -> None:
    if hasattr(os, "register_at_fork"):
        os.register_at_fork(after_in_child=_reset_for_fork)


_register_fork_hook()
