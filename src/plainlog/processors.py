"""
Processors, formatters and handlers.

Processors transform a log record in the Core thread. Formatters turn a
record into a string. Handlers are processors that perform output.
"""

import asyncio
import json
import logging
import os
import pathlib
import stat
import sys
import time
from asyncio import CancelledError
from collections import deque
from concurrent.futures import Future
from contextlib import suppress
from copy import copy, deepcopy
from datetime import datetime, timezone
from functools import lru_cache
from typing import IO, Any, Callable

from . import _env
from ._base import Record, UniversalProcessorProtocol
from ._dev import ConsoleRenderer  # noqa
from ._utils import (
    eval_dict,
    eval_format,
    eval_lambda_dict,
    get_processed_extra,
    handle_close,
)

start_time: float = time.time()


def eval_lambda_extra(record: Record) -> Record:
    extra = record.get("extra", {})
    eval_lambda_dict(extra)

    return record


def eval_extra(record: Record) -> Record:
    extra = record.get("extra", {})
    eval_dict(extra)

    return record


def remove_extra_items(*args) -> Callable:
    def remover(record: Record) -> Record:
        for arg in args:
            arg = str(arg)
            record["extra"].pop(arg, None)
        return record

    return remover


def _redact(mask: str, matches: Callable[[str], bool]) -> Callable:
    def redact_value(key: Any, value: Any) -> Any:
        if isinstance(value, dict):
            return {k: redact_value(k, v) for k, v in value.items()}
        if isinstance(value, list):
            return [redact_value(None, item) for item in value]
        if isinstance(value, tuple):
            return tuple(redact_value(None, item) for item in value)
        if isinstance(key, str) and matches(key):
            return mask
        return value

    def redactor(record: Record) -> Record:
        extra = record.get("extra")
        if extra:
            record["extra"] = redact_value(None, extra)
        return record

    return redactor


def redact_fields(*fields, mask="***REDACTED***") -> Callable:
    names = {str(field).lower() for field in fields}
    return _redact(mask, lambda key: key.lower() in names)


def redact_by_pattern(*patterns, mask="***REDACTED***") -> Callable:
    needles = tuple(str(pattern).lower() for pattern in patterns)
    return _redact(mask, lambda key: any(needle in key.lower() for needle in needles))


# Filter, are processors, but do not modify record, only return {} if filterd out


def filter_None(record: Record) -> Record:
    if record["name"] is None:
        return {}
    return record


def filter_all(record: Record) -> Record:
    return {}


def filter_by_name(parent) -> Callable:
    def namefilter(record: Record) -> Record:
        name = record["name"]
        if name is None:
            return {}
        elif name.startswith(parent):
            return {}
        return record

    return namefilter


def allow_by_name(parent) -> Callable:
    def allow_name(record: Record) -> Record:
        name = record["name"]
        if name and name.startswith(parent):
            return record
        return {}

    return allow_name


def filter_by_level(level_per_module) -> Callable:
    def levelfilter(record: Record) -> Record:
        name = record["name"]

        while name:
            level = level_per_module.get(name, None)
            if level is False:
                return {}
            if level is not None:
                if record["level"] < level:
                    return {}
            index = name.rfind(".")
            name = name[:index] if index != -1 else ""

        return record

    return levelfilter


class FilterList:
    def __init__(self, blacklist, whitelist=None) -> None:
        self._whitelist = frozenset() if whitelist is None else frozenset(whitelist)
        self._blacklist = frozenset(blacklist)
        self._partition_cache: dict = {}

    def partition(self, name: str) -> set:
        if name in self._partition_cache:
            return self._partition_cache[name]
        part_set = set()
        parts = name.split(".")
        for i in range(1, len(parts) + 1):
            part_set.add(".".join(parts[:i]))
        self._partition_cache[name] = part_set

        return part_set

    def __call__(self, record: Record) -> Record:
        name = record["name"]
        name_parts = self.partition(name)

        whitelist = name_parts.isdisjoint(self._whitelist)
        blacklist = not name_parts.isdisjoint(self._blacklist)

        if whitelist and blacklist:
            return {}
        return record


class WhitelistLevel:
    def __init__(self, whitelist) -> None:
        self._whitelist_names = frozenset(whitelist)
        self._whitelist_levels = whitelist

    @staticmethod
    @lru_cache
    def partition(name) -> set:
        part_set = set()
        parts = name.split(".")
        for i in range(1, len(parts) + 1):
            part_set.add(".".join(parts[:i]))

        return part_set

    def __call__(self, record: Record) -> Record:
        name = record["name"]
        level_no = record["level"]
        name_parts = self.partition(name)

        whitelisted: bool = not name_parts.isdisjoint(self._whitelist_names)
        if not whitelisted:
            return {}
        # else check level
        for name in name_parts:
            level = self._whitelist_levels.get(name)
            if level is not None:
                if level_no < level:
                    return {}

        return record


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


def format_message(record: Record) -> Record:
    message = record.get("message", None)
    if message is None:
        msg = record.get("msg", "")
        extra = record.get("extra", {})
        message = str(msg)
        if isinstance(msg, str) and extra:
            message = eval_format(msg, extra)

        record["message"] = message

    return record


def print_processor_error(record: Record) -> Record:
    error_message = record.get("processor_error_message", None)
    error_processor_name = record.get("processor_error_name_repr", None)
    if error_message is not None:
        print(
            f"Got processor {error_processor_name} error: {error_message}.",
            file=sys.stderr,
            flush=True,
        )

    return record


class SimpleFormatter:
    DEFAULT_FORMAT = (
        "{datetime:%Y-%m-%d %H:%M:%S.%f} {level_name:<8} [{name}] {message}{extra}"
    )

    def __init__(self, fmt=None):
        self._fmt = fmt if fmt is not None else self.DEFAULT_FORMAT

    def __call__(self, record: Record) -> Record:
        data = copy(record)
        data["datetime"] = datetime.fromtimestamp(data.pop("created"), tz=timezone.utc)
        format_message(data)
        extra = get_processed_extra(record)
        data["extra"] = "" if not extra else f" {extra}"
        message = self._fmt.format_map(data)
        record["message"] = message

        return record


class JsonFormatter:
    DEFAULT_ADDITIONAL_KEYS = (
        "file_name",
        "file_path",
        "function",
        "line",
        "module",
        "process_id",
        "process_name",
        "thread_id",
        "thread_name",
    )

    def __init__(
        self,
        converter=None,
        indent=None,
        separators=None,
        sort_keys=False,
        additional_keys=None,
    ):
        if converter is None:
            converter = str
        self._converter = converter
        self._indent = indent
        self._separators = separators
        self._sort_keys = sort_keys
        if additional_keys is None:
            self._additional_keys = self.DEFAULT_ADDITIONAL_KEYS
        else:
            self._additional_keys = additional_keys

    def __call__(self, record: Record) -> Record:
        exception = record.get("exception")

        if exception is not None:
            exception = {
                "type": None if exception.type is None else exception.type.__name__,
                "value": exception.value,
                "traceback": bool(exception.traceback),
            }

        format_message(record)
        extra = get_processed_extra(record)

        serializable = {
            "message": record["message"],
            "name": record["name"],
            "created": record["created"],
            "level_name": record["level_name"],
            "level_no": record["level"],
            "extra": extra,
            "process_id": record["process_id"],
            "process_name": record["process_name"],
        }
        if exception:
            serializable["exception"] = exception
        for key in self._additional_keys:
            value = record.get(key)
            if value is not None:
                serializable[key] = value
        message = json.dumps(
            serializable,
            default=self._converter,
            ensure_ascii=False,
            indent=self._indent,
            separators=self._separators,
            sort_keys=self._sort_keys,
        )
        record["message"] = message

        return record


# ---------------------------------------------------------------------------
# Processing Handlers
# ---------------------------------------------------------------------------


class SubProcessor:
    """Processor that runs sub processors in order on a copy of the record.

    Args:
        processors: List of callables run one after another.

    Example::

        from plainlog.processors import Stream, SubProcessor, format_message

        handler = SubProcessor([format_message, Stream()])
    """

    def __init__(self, processors=None):
        self._processors = () if processors is None else tuple(processors)

    def __call__(self, record: Record) -> Record:
        exception = record.get("exception")
        record = deepcopy(record)
        # deepcopy strips tracebacks via RecordException.__reduce__, restore it
        if exception is not None:
            record["exception"] = exception
        for processor in self._processors:
            record = processor(record)
            if not record:  # stop processing
                return record

        return record

    def close(self) -> None:
        for processor in self._processors:
            with suppress(Exception):
                handle_close(processor)


class Stream:
    """Writes a record's formatted ``message`` to a file-like stream.

    Args:
        stream: A file-like object with a ``write`` method.
            Defaults to ``sys.stderr``.
    """

    def __init__(self, stream=None) -> None:
        if stream is None:
            stream = sys.stderr
        self._stream = stream
        self._flushable = callable(getattr(stream, "flush", None))
        self.terminator = "\n"

    def __call__(self, record: Record) -> Record:
        self.write(record["message"])

        return record

    def close(self) -> None:
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}"

    def write(self, message) -> None:
        self._stream.write(message + self.terminator)
        # self._stream.write(self.terminator)
        if self._flushable:
            self._stream.flush()


class WrapStandardHandler:
    """Wraps a stdlib ``logging.Handler`` to receive plainlog records.

    Converts plainlog record dicts into ``logging.LogRecord`` instances
    and forwards them to the wrapped handler.

    Args:
        handler: A stdlib ``logging.Handler`` instance.
    """

    factory = logging.getLogRecordFactory()

    def __init__(self, handler) -> None:
        self._handler = handler

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(handler={self._handler!r})"

    def __call__(self, record: Record) -> Record:
        msg = str(record.get("msg", ""))
        message = str(record.get("message", msg))
        exc = record.get("exception")
        file_path = record["file"].path if "file" in record else ""
        lrecord = self.factory(
            record["name"],
            record["level"],
            file_path,
            record.get("line", 0),
            message,
            (),
            (exc.type, exc.value, exc.traceback) if exc else None,
            record.get("function", ""),
            {"extra": record["extra"]},
        )
        if exc:
            lrecord.exc_text = "\n"
        self._handler.handle(lrecord)

        return record

    def close(self) -> None:
        self._handler.close()


class FingersCrossed:
    """Buffers records until a threshold level triggers a flush.

    Records are buffered up to ``buffer_size``. When a record at or above
    ``action_level`` arrives, all buffered records plus the triggering
    record are forwarded to the wrapped handler.

    Args:
        handler: Wrapped processor with a ``close()`` method to flush to.
        action_level: Log level number that triggers the flush.
            Defaults to 40 (ERROR).
        buffer_size: Maximum number of records to buffer.
            Defaults to 1.
        reset: If ``True``, the handler resets after each flush and
            buffers again. Defaults to ``False``.

    Inspired by Monolog's FingersCrossedHandler.
    """

    def __init__(
        self,
        processor: UniversalProcessorProtocol,
        action_level=None,
        buffer_size=None,
        reset=None,
    ) -> None:
        self._processor = processor
        action_level = (
            40 if action_level is None else action_level
        )  # default action_level ERROR
        self._level = logging._checkLevel(action_level)  # type: ignore
        buffer_size = 1 if buffer_size is None else int(buffer_size)
        self.buffered_records: deque = deque(maxlen=buffer_size)
        self._action_triggered = False
        self._reset = False if reset is None else reset

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(action_level={self._level!r}, processor={self._processor!r})"

    def enqueue(self, record):
        if self._action_triggered:
            self._processor(record)
        else:
            self.buffered_records.append(record)
            return record["level"] >= self._level

        return False

    def rollover(self) -> None:
        while self.buffered_records:
            record = self.buffered_records.popleft()
            self._processor(record)

        self._action_triggered = not self._reset

    def __call__(self, record: Record) -> Record:
        if self.enqueue(record):
            self.rollover()

        return record

    def close(self) -> None:
        handle_close(self._processor)


class FileWriter:
    """Writes formatted log records to a file.

    Supports delayed file creation and log rotation detection via inode
    watching (useful with logrotate).

    Args:
        path: File path to write to.
        delay: Defer file creation until the first log record.
        watch: Reopen the file if the inode changes (log rotation).
        mode: File open mode. Defaults to ``"a"``.
        buffering: File buffering. Defaults to 1 (line buffered).
        encoding: File encoding. Defaults to ``"utf8"``.
    """

    def __init__(
        self,
        path,
        *,
        delay=False,
        watch=False,
        mode="a",
        buffering=1,
        encoding="utf8",
    ) -> None:
        self._path = pathlib.Path(path)
        self._encoding = encoding
        self._mode = mode
        self._buffering = buffering
        self._watch = watch

        self._file: IO[Any] | None = None

        self._file_dev = -1
        self._file_ino = -1
        self.terminator = "\n"

        if not delay:
            self._create_file()

    def __call__(self, record: Record) -> Record:
        self.write(record.get("message", ""))

        return record

    def write(self, message) -> None:
        if self._file is None:
            self._create_file()

        if self._watch:
            self._reopen_if_needed()

        self._file.write(message)  # type: ignore
        self._file.write(self.terminator)  # type: ignore

    def close(self) -> None:
        if self._watch:
            self._reopen_if_needed()

        self._close_file()

    def _create_file(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self._path.open(
            mode=self._mode, encoding=self._encoding, buffering=self._buffering
        )

        if self._watch:
            fileno: int = self._file.fileno()
            result = os.stat(fileno)
            self._file_dev = result[stat.ST_DEV]
            self._file_ino = result[stat.ST_INO]

    def _close_file(self) -> None:
        if self._file:
            self._file.flush()
            self._file.close()

        self._file = None
        self._file_dev = -1
        self._file_ino = -1

    def _reopen_if_needed(self) -> None:
        if not self._file:
            return

        try:
            result = self._path.stat()
        except FileNotFoundError:
            result = None

        if (
            not result
            or result[stat.ST_DEV] != self._file_dev
            or result[stat.ST_INO] != self._file_ino
        ):
            self._close_file()
            self._create_file()


class AsyncBridge:
    """Base handler for async integrations.

    Schedules writes via ``asyncio.run_coroutine_threadsafe`` on the
    given event loop. Subclasses must override `write()` to perform
    the actual async I/O.

    Args:
        loop: The ``asyncio.AbstractEventLoop`` to schedule writes on.
            If ``None`` (default) and a loop is currently running in the
            building thread, that loop is captured; otherwise the handler
            is a no-op until a loop is supplied. Construction never raises.
    """

    def __init__(self, loop=None) -> None:
        if loop is None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
        self.loop = loop
        self.terminator = "\n"
        self._futures: set = set()

    def __call__(self, record: Record) -> Record:
        message = record.get("message", "")
        loop = self.loop
        if loop is None or not loop.is_running():
            return record
        try:
            future = asyncio.run_coroutine_threadsafe(self.write(message), loop)
        except RuntimeError:
            return record
        done = [f for f in self._futures if f.done()]
        for f in done:
            self._futures.discard(f)
        self._futures.add(future)

        return record

    async def write(self, message):  # pragma: no cover
        pass

    def close(self) -> None:
        for future in self._futures:
            try:
                if isinstance(future, Future):
                    future.result(_env.DEFAULT_WAIT_TIMEOUT)
                else:
                    future.result()
            except (TimeoutError, CancelledError):
                pass
        self._futures.clear()
