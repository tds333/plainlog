# SPDX-FileCopyrightText: 2023 Wolfgang Langner <tds333@mailbox.org>
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
import json
from datetime import datetime, timezone

from ._utils import eval_format, get_processed_extra


def format_message(record):
    msg = record.get("msg", "")
    message = record.get("message", "")
    extra = record.get("extra", {})
    if isinstance(msg, str) and extra:
        message = eval_format(msg, extra)
    if not message and msg:
        message = str(msg)

    return message


class SimpleFormatter:
    DEFAULT_FORMAT = "{datetime} {level_name:<8} [{name}] {message}"

    def __init__(self, fmt=None):
        self._fmt = fmt if fmt is not None else self.DEFAULT_FORMAT

    def __call__(self, record):
        data = record.copy()
        data["datetime"] = datetime.fromtimestamp(data.pop("created"), tz=timezone.utc)
        data["message"] = format_message(record)
        data["extra"] = get_processed_extra(record)
        message = self._fmt.format_map(data)

        return message


class DefaultFormatter:
    DEFAULT_FORMAT = "{datetime:%H:%M:%S.%f} {level_name:<8} [{name}] {message} {extra}"

    def __init__(self):
        self._fmt = DefaultFormatter.DEFAULT_FORMAT

    def __call__(self, record):
        data = record.copy()
        data["datetime"] = datetime.fromtimestamp(data.pop("created"), tz=timezone.utc)
        data["message"] = format_message(record)
        extra = get_processed_extra(record)
        data["extra"] = "" if not extra else extra
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

    def __call__(self, record):
        exception = record.get("exception")

        if exception is not None:
            exception = {
                "type": None if exception.type is None else exception.type.__name__,
                "value": exception.value,
                "traceback": bool(exception.traceback),
            }

        message = format_message(record)
        extra = get_processed_extra(record)

        serializable = {
            "message": message,
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

        return json.dumps(
            serializable,
            default=self._converter,
            ensure_ascii=False,
            indent=self._indent,
            separators=self._separators,
            sort_keys=self._sort_keys,
        )
