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
from typing import Any, Dict, Protocol, IO, Optional

from concurrent.futures import Future

from . import _env
from ._dev import ConsoleRenderer
from .formatters import (
    DefaultFormatter,
    JsonFormatter,
    SimpleFormatter,
)
from .processors import context_to_extra, kwargs_to_extra, eval_extra
from ._recattrs import Record, HandlerProtocol


# class HandlerProtocol(Protocol):
#     def __call__(self, record: Record) -> Record: ...

#     def preprocess(self, record: Record) -> Record: ...

#     def close(self) -> None: ...


class BaseHandler:
    def preprocess(self, record: Record) -> Record:
        return record

    def process(self, record: Record) -> Record:
        return record

    def close(self) -> None:
        pass


class ProcessingHandler:
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
    def __init__(self, stream=None) -> None:
        if stream is None:
            stream = sys.stdout
        super().__init__(stream, DefaultFormatter())


class ConsoleHandler(StreamHandler):
    def __init__(self, stream=None, colors=True) -> None:
        if stream is None:
            stream = sys.stdout
        super().__init__(stream, ConsoleRenderer(colors=colors))


class WrapStandardHandler:
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
            self.last_future.result(_env.DEFAULT_WAIT_TIMEOUT)  # type: ignore

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(formatter={self._formatter.__class__.__name__})"
        )
