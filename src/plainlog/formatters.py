# SPDX-FileCopyrightText: 2023 Wolfgang Langner <tds333@mailbox.org>
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
import io
import traceback
import contextlib
import json
from collections import defaultdict

from ._dev import ConsoleRenderer


def format_message(record):
    preformatted = record.get("preformatted", False)
    message = record.get("message", "")
    if preformatted:
        return message
    msg = record.get("msg", "")
    args = record.get("args", [])
    kwargs = record.get("kwargs", {})
    if msg and (args or kwargs):
        message = msg.format(*args, **kwargs)
    
    return message


class SimpleFormatter:

    DEFAULT_FORMAT = "{datetime} {level.name:<8} [{name}] {message}"

    def __init__(self, fmt=None):
        self._fmt = fmt if fmt is not None else self.DEFAULT_FORMAT

    def __call__(self, record):
        message = format_message(record)
        data = record.copy()
        data["message"] = message
        message = self._fmt.format_map(data)

        return message


class DefaultFormatter:

    DEFAULT_FORMAT = "{datetime:%H:%M:%S.%f} {level.name:<8} [{name}] {message} {extra}"

    def __init__(self):
        self._fmt = DefaultFormatter.DEFAULT_FORMAT

    def __call__(self, record):
        message = format_message(record)
        data = record.copy()
        extra = data.get("extra", {})
        if not extra:
            data["extra"] = ""
        data["message"] = message
        message = self._fmt.format_map(data)

        return message


_DEFAULT_FORMAT = "{datetime:%H:%M:%S.%f} {level.name:<8} [{name}] {message} {extra}"


def default_formatter(record, fmt=_DEFAULT_FORMAT):
    message = format_message(record)
    data = record.copy()
    extra = data.get("extra", {})
    if not extra:
        data["extra"] = ""
    data["message"] = message
    #message = _DEFAULT_FORMAT.format_map(data)
    message = fmt.format_map(data)

    return message


class JsonFormatter:

    DEFAULT_ADDITIONAL_KEYS = ("file_name", "file_path", "function", "line", "module", "process_id", "process_name", "thread_id", "thread_name")
    
    def __init__(self, converter=None, indent=None, separators=None, sort_keys=False, additional_keys=None):
        if converter is None:
            converter = str
        self._converter = converter
        self._indent = indent
        self._separators = separators
        self._sort_keys = sort_keys
        if additional_keys is None:
            self._additional_keys = self.DEFAULT_ADDITIONAL_KEYS

    def __call__(self, record):
        exception = record.get("exception")

        if exception is not None:
            exception = {
                "type": None if exception.type is None else exception.type.__name__,
                "value": exception.value,
                "traceback": bool(exception.traceback),
            }

        message = format_message(record)

        serializable = {
            "message": message,
            "name": record["name"],
            "datetime": record["datetime"].isoformat(),
            "elapsed": {
                "repr": record["elapsed"],
                "seconds": record["elapsed"].total_seconds(),
            },
            "level": {
                "name": record["level"].name,
                "no": record["level"].no,
            },
            "exception": exception,
            "extra": record["extra"],
            #"time": {"repr": record["time"], "timestamp": record["time"].timestamp()},
        }
        for key in self._additional_keys:
            value = record.get(key)
            if value is not None:
                serializable[key] = value

        return json.dumps(serializable, default=self._converter, ensure_ascii=False, indent=self._indent, separators=self._separators, sort_keys=self._sort_keys)


# def std_format_exception(ei):
#     """
#     Format and return the specified exception information as a string.

#     This default implementation just uses
#     traceback.print_exception()
#     """
#     sio = io.StringIO()
#     tb = ei[2]
#     traceback.print_exception(ei[0], ei[1], tb, None, sio)
#     s = sio.getvalue()
#     sio.close()
#     if s[-1:] == "\n":
#         s = s[:-1]

#     return s


# def std_format(record):
#     """
#     Format the specified record as text.

#     The record's attribute dictionary is used as the operand to a
#     string formatting operation which yields the returned string.
#     Before formatting the dictionary, a couple of preparatory steps
#     are carried out. The message attribute of the record is computed
#     using LogRecord.getMessage(). If the formatting string uses the
#     time (as determined by a call to usesTime(), formatTime() is
#     called to format the event time. If there is exception information,
#     it is formatted using formatException() and appended to the message.
#     """
#     message = record.get("message", "")
#     args = record.get("args", [])
#     kwargs = record.get("kwargs", {})
#     exc_info = record.get("exc_info")
#     stack_info = record.get("stack_info")

#     with contextmanager.suppress(Exception):
#         s = message.format(*args, **kwargs)
#     if exc_info:
#         exc_text = std_format_exception(exc_info)
#     if exc_text:
#         if s[-1:] != "\n":
#             s = s + "\n"
#         s = s + exc_text
#     if stack_info:
#         if s[-1:] != "\n":
#             s = s + "\n"
#         s = s + stack_info

#     return s
