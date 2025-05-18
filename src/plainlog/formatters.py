# SPDX-FileCopyrightText: 2023 Wolfgang Langner <tds333@mailbox.org>
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
import json
from ._utils import eval_format


def format_message(record):
    preformatted = record.get("preformatted", False)
    message = record.get("message", "")
    if preformatted:
        return message
    msg = record.get("msg", "")
    args = record.get("args", [])
    kwargs = record.get("kwargs", {})
    if msg and (args or kwargs):
        message = eval_format(msg, args, kwargs)

    return message


class SimpleFormatter:
    DEFAULT_FORMAT = "{datetime} {level.name:<8} [{name}] {message}"

    def __init__(self, fmt=None):
        self._fmt = fmt if fmt is not None else self.DEFAULT_FORMAT

    def __call__(self, record):
        data = record.copy()
        data["message"] = format_message(record)
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
            "timestamp": record["datetime"].timestamp(),
            "level_name": record["level"].name,
            "level_no": record["level"].no,
            "extra": record["extra"],
            "process_id": record["process_id"],
            "process_name": record["process_name"],
        }
        if exception:
            serializable["exception"] = exception
        for key in self._additional_keys:
            value = record.get(key)
            if value is not None:
                serializable[key] = value

        return json.dumps(
            serializable,
            default=self._converter,
            ensure_ascii=False,
            indent=self._indent,
            separators=self._separators,
            sort_keys=self._sort_keys,
        )
