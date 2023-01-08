# SPDX-FileCopyrightText: 2023 Wolfgang Langner <tds333@mailbox.org>
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
import sys
import json
import operator
import logging
from collections import deque
from typing import (
    Any,
    Callable,
    ClassVar,
    Collection,
    NamedTuple,
    Sequence,
    TextIO,
)
from .formatters import SimpleFormatter, ConsoleRenderer, JsonFormatter, DefaultFormatter, default_formatter
from ._file_handler import FileHandler
from ._defaults import PLAINLOG_LEVEL


class StreamHandler:

    def __init__(self, stream=None, formatter=None):
        if stream is None:
            stream = sys.stderr
        self._stream = stream
        self._formatter = SimpleFormatter() if formatter is None else formatter
        self._flushable = callable(getattr(stream, "flush", None))
        self.terminator = "\n"
    
    def __call__(self, record):
        message = self._formatter(record)
        self.write(message)
    
    def __repr__(self):
        return f"{self.__class__.__name__}(formatter={self._formatter.__class__.__name__})"

    def write(self, message):
        self._stream.write(message + self.terminator)
        #self._stream.write(self.terminator)
        if self._flushable:
            self._stream.flush()


class DefaultHandler(StreamHandler):

    def __init__(self, stream=None):
        if stream is None:
            stream = sys.stdout
        super().__init__(stream, default_formatter)


class ConsoleHandler(StreamHandler):

    def __init__(self, stream=None, colors=True):
        if stream is None:
            stream = sys.stdout
        super().__init__(stream, ConsoleRenderer(colors=colors))


class WrapStandardHandler:

    def __init__(self, handler):
        self._handler = handler

    def __call__(self, record):
        message = str(record.get("message", ""))
        exc = record.get("exception")
        record = logging.getLogger().makeRecord(
            record["name"],
            record["level"].no,
            "", #record["file"].path,
            0, #record["line"],
            message,
            (),
            (exc.type, exc.value, exc.traceback) if exc else None,
            "", #record["function"],
            {"extra": record["extra"]},
        )
        if exc:
            record.exc_text = "\n"
        self._handler.handle(record)

    def close(self):
        self._handler.close()


class JsonHandler(StreamHandler):

    def __init__(self, stream=None, converter=None, indent=None, separators=None, sort_keys=False, additional_keys=None):
        formatter = JsonFormatter(converter=converter, indent=indent, separators=separators, sort_keys=sort_keys, additional_keys=additional_keys)
        super().__init__(stream, formatter)


class FingersCrossedHandler:

    def __init__(self, handler, action_level=None, buffer_size=None, reset=None):
        self._handler = handler
        action_level = 40 if action_level is None else action_level  # default action_level ERROR
        self._level = logging._checkLevel(action_level)
        buffer_size = 1 if buffer_size is None else int(buffer_size)
        self.buffered_records = deque(maxlen=buffer_size)
        self._action_triggered = False
        self._reset = False if reset is None else reset

    def close(self):
        if hasattr(self._handler, "close") and callable(self._handler.close):
            self._handler.close()

    def enqueue(self, record):
        if self._action_triggered:
            self._handler(record)
        else:
            self.buffered_records.append(record)
            return record["level"].no >= self._level

        return False

    def rollover(self):
        while self.buffered_records:
            record = self.buffered_records.popleft()
            self._handler(record)

        self._action_triggered = not self._reset
    
    def __call__(self, record):
        if self.enqueue(record):
            self.rollover()


DEFAULT_HANDLERS = ({"handler": DefaultHandler(), "level": PLAINLOG_LEVEL}, )
