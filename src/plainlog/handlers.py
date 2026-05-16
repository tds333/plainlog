# SPDX-FileCopyrightText: 2023 Wolfgang Langner <tds333@mailbox.org>
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
import asyncio
import logging
import os
import pathlib
import stat
import sys
from collections import deque
from concurrent.futures import Future
from typing import IO, Any

from . import _env
from ._base import HandlerProtocol, Record
from ._dev import ConsoleRenderer
from .formatters import (
    DefaultFormatter,
    JsonFormatter,
    SimpleFormatter,
)
from .processors import add_caller_info


class BaseHandler:
    """Minimal handler that passes records through unchanged.

    Implements the :class:`HandlerProtocol` with no-op methods.
    Useful as a base class or placeholder.
    """

    def preprocess(self, record: Record) -> Record:
        return record

    def process(self, record: Record) -> Record:
        return record

    def close(self) -> None:
        pass


class ProcessingHandler:
    """Handler that runs preprocessors and processors around a wrapped handler.

    Preprocessors execute in the application thread before the record is
    enqueued. Processors execute in the Core's background thread after
    dequeueing.

    Args:
        preprocessors: List of callables run before enqueueing.
        processors: List of callables run after dequeueing.
        handler: Wrapped :class:`HandlerProtocol` to call after processors.

    Example::

        from plainlog.handlers import ProcessingHandler, StreamHandler
        from plainlog.processors import add_caller_info

        handler = ProcessingHandler(
            preprocessors=[add_caller_info],
            handler=StreamHandler(),
        )
    """

    def __init__(self, preprocessors=None, processors=None, handler=None):
        self._preprocessors = [] if preprocessors is None else preprocessors
        self._processors = [] if processors is None else processors
        self._handler = handler

    def preprocess(self, record: Record) -> Record:
        for preprocessor in self._preprocessors:
            record = preprocessor(record)
            if not record:
                return record

        return record

    def process(self, record: Record) -> Record:
        for processor in self._processors:
            record = processor(record)
            if not record:  # stop processing
                return record
        if self._handler is not None:
            record = self._handler.process(record)

        return record

    def close(self) -> None:
        if self._handler is not None:
            self._handler.close()


class CollectHandler:
    """Handler that dispatches records to multiple sub-handlers.

    Each record is passed through every sub-handler's ``preprocess`` and
    ``process`` methods in order. If any handler returns a falsy record,
    processing stops.

    Args:
        handlers: Iterable of :class:`HandlerProtocol` instances.
    """

    def __init__(self, handlers=None):
        self._handlers = [] if handlers is None else handlers

    def preprocess(self, record: Record) -> Record:
        for handler in self._handlers:
            record = handler.preprocess(record)
            if not record:  # stop processing
                return record

        return record

    def process(self, record: Record) -> Record:
        for handler in self._handlers:
            record = handler.process(record)
            if not record:  # stop processing
                return record

        return record

    def close(self) -> None:
        for handler in self._handlers:
            handler.close()


class StreamHandler:
    """Writes formatted log records to a file-like stream.

    By default writes to ``sys.stderr`` with a :class:`SimpleFormatter`.

    Args:
        stream: A file-like object with a ``write`` method.
            Defaults to ``sys.stderr``.
        formatter: Callable that takes a record and returns a string.
            Defaults to :class:`SimpleFormatter`.
    """

    def __init__(self, stream=None, formatter=None) -> None:
        if stream is None:
            stream = sys.stderr
        self._stream = stream
        self._formatter = SimpleFormatter() if formatter is None else formatter
        self._flushable = callable(getattr(stream, "flush", None))
        self.terminator = "\n"

    def preprocess(self, record: Record) -> Record:
        return record

    def process(self, record: Record) -> Record:
        return self(record)

    def close(self) -> None:
        pass

    def __call__(self, record: Record) -> Record:
        message = self._formatter(record)
        self.write(message)

        return record

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(formatter={self._formatter.__class__.__name__})"
        )

    def write(self, message) -> None:
        self._stream.write(message + self.terminator)
        # self._stream.write(self.terminator)
        if self._flushable:
            self._stream.flush()


class DefaultHandler(StreamHandler):
    """StreamHandler that writes to ``sys.stdout`` with a :class:`DefaultFormatter`."""

    def __init__(self, stream=None) -> None:
        if stream is None:
            stream = sys.stdout
        super().__init__(stream, DefaultFormatter())


class ConsoleHandler(StreamHandler):
    """StreamHandler with colorized output via :class:`ConsoleRenderer`.

    Intended for interactive development. Color codes can be disabled.

    Args:
        stream: Output stream. Defaults to ``sys.stdout``.
        colors: Enable ANSI color codes.
    """

    def __init__(self, stream=None, colors=True) -> None:
        if stream is None:
            stream = sys.stdout
        super().__init__(stream, ConsoleRenderer(colors=colors))


class DevelopHandler(ConsoleHandler):
    """ConsoleHandler that enriches records with caller info during preprocessing.

    Automatically adds function name, line number, module, and file path
    to each record via :func:`add_caller_info`.
    """

    def preprocess(self, record: Record) -> Record:
        record = add_caller_info(record, level=4)
        return record


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

    def preprocess(self, record: Record) -> Record:
        return record

    def process(self, record: Record) -> Record:
        return self(record)

    def __call__(self, record: Record) -> Record:
        message = str(record.get("message", ""))
        exc = record.get("exception")
        file_path = record["file"].path if "file" in record else ""
        lrecord = self.factory(
            record["name"],
            record["level"].no,
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


class JsonHandler(StreamHandler):
    """StreamHandler that outputs one JSON object per log record.

    Configures a :class:`JsonFormatter` with the given parameters.

    Args:
        stream: Output stream. Defaults to ``sys.stderr``.
        converter: Custom JSON serializer for non-standard types.
        indent: JSON indent level. ``None`` for compact output.
        separators: Custom ``(item_sep, key_sep)`` tuple.
        sort_keys: Sort JSON keys alphabetically.
        additional_keys: Extra record keys to include in the JSON output.
    """

    def __init__(
        self,
        stream=None,
        converter=None,
        indent=None,
        separators=None,
        sort_keys=False,
        additional_keys=None,
    ) -> None:
        formatter = JsonFormatter(
            converter=converter,
            indent=indent,
            separators=separators,
            sort_keys=sort_keys,
            additional_keys=additional_keys,
        )
        super().__init__(stream, formatter)


class FingersCrossedHandler:
    """Buffers records until a threshold level triggers a flush.

    Records are buffered up to ``buffer_size``. When a record at or above
    ``action_level`` arrives, all buffered records plus the triggering
    record are forwarded to the wrapped handler.

    Args:
        handler: Wrapped :class:`HandlerProtocol` to flush to.
        action_level: Log level number that triggers the flush.
            Defaults to 40 (ERROR).
        buffer_size: Maximum number of records to buffer.
            Defaults to 1.
        reset: If ``True``, the handler resets after each flush and
            buffers again. Defaults to ``False``.

    Inspired by Monolog's FingersCrossedHandler.
    """

    def __init__(
        self, handler: HandlerProtocol, action_level=None, buffer_size=None, reset=None
    ) -> None:
        self._handler = handler
        action_level = (
            40 if action_level is None else action_level
        )  # default action_level ERROR
        self._level = logging._checkLevel(action_level)  # type: ignore
        buffer_size = 1 if buffer_size is None else int(buffer_size)
        self.buffered_records: deque = deque(maxlen=buffer_size)
        self._action_triggered = False
        self._reset = False if reset is None else reset

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(action_level={self._level!r}, handler={self._handler!r})"

    def enqueue(self, record):
        if self._action_triggered:
            self._handler.process(record)
        else:
            self.buffered_records.append(record)
            return record["level"].no >= self._level

        return False

    def rollover(self) -> None:
        while self.buffered_records:
            record = self.buffered_records.popleft()
            self._handler.process(record)

        self._action_triggered = not self._reset

    def preprocess(self, record: Record) -> Record:
        return self._handler.preprocess(record)

    def process(self, record: Record) -> Record:
        if self.enqueue(record):
            self.rollover()

        return record

    def close(self) -> None:
        self._handler.close()


class FileHandler:
    """Writes formatted log records to a file.

    Supports delayed file creation and log rotation detection via inode
    watching (useful with logrotate).

    Args:
        path: File path to write to.
        formatter: Callable that takes a record and returns a string.
            Defaults to :class:`SimpleFormatter`.
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
        formatter=None,
        delay=False,
        watch=False,
        mode="a",
        buffering=1,
        encoding="utf8",
    ) -> None:
        self._path = pathlib.Path(path)
        self._formatter = SimpleFormatter() if formatter is None else formatter
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

    def preprocess(self, record: Record) -> Record:
        return record

    def process(self, record: Record) -> Record:
        message = self._formatter(record)
        self.write(message)

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


class AsyncHandler:
    """Base handler for async integrations.

    Schedules writes via ``asyncio.run_coroutine_threadsafe`` on the
    given event loop. Subclasses must override :meth:`write` to perform
    the actual async I/O.

    Args:
        loop: The ``asyncio.AbstractEventLoop`` to schedule writes on.
            Defaults to the currently running loop.
        formatter: Callable that takes a record and returns a string.
            Defaults to :class:`SimpleFormatter`.
    """

    def __init__(self, loop=None, formatter=None) -> None:
        self.loop = asyncio.get_running_loop() if loop is None else loop
        self._formatter = SimpleFormatter() if formatter is None else formatter
        self.terminator = "\n"
        self.last_future: Future[Any] | None = None

    def preprocess(self, record: Record) -> Record:
        return record

    def process(self, record: Record) -> Record:
        message = self._formatter(record)
        if self.loop.is_running():
            self.last_future = asyncio.run_coroutine_threadsafe(
                self.write(message), self.loop
            )

        return record

    async def write(self, message):
        pass

    def close(self) -> None:
        if self.last_future is not None:
            self.last_future.result(_env.DEFAULT_WAIT_TIMEOUT)

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(formatter={self._formatter.__class__.__name__})"
        )
