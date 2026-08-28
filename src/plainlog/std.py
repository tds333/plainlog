# SPDX-FileCopyrightText: 2023 Wolfgang Langner <tds333@mailbox.org>
#
# SPDX-License-Identifier: Apache-2.0 OR MIT

import logging
from typing import Union

from ._base import RecordException
from ._logger import logger_core, plainlog_context


class StdInterceptHandler(logging.Handler):
    _core = logger_core
    _known_keys = {
        "args",
        "created",
        "exc_text",
        "exc_info",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
        "taskName",
    }

    def emit(self, record) -> None:
        core = self._core
        level = record.levelno

        if core.min_level_no > level or self.level > level:
            return

        extra: dict = {}
        for key, value in record.__dict__.items():
            if key not in self._known_keys:
                extra[key] = value

        log_record = {
            "level": level,
            "level_name": logging.getLevelName(level),
            "msg": record.msg,  # raw message as in std logging
            "message": record.getMessage(),
            "name": record.name,
            "created": record.created,
            "process_id": record.process,
            "process_name": record.processName,
            "extra": {**extra, **plainlog_context.get({})},
            "args": record.args,
            "exception": (
                RecordException(*record.exc_info) if record.exc_info else None
            ),
            "preformatted": True,
            "function": record.funcName,
            "line": record.lineno,
            "module": record.module,
            "path": record.pathname,
            "thread_id": record.thread,
            "thread_name": record.threadName,
            "stack_info": record.stack_info,
            "exc_text": record.exc_text,
        }
        # since Python 3.12 there is taskName available
        if hasattr(record, "taskName"):  # pragma: no cover
            log_record["task_name"] = record.taskName

        core.log(log_record)


def set_as_root_handler(level: Union[int, str] = logging.NOTSET) -> logging.Handler:
    handler = StdInterceptHandler(level)
    root = logging.getLogger(name="root")
    root.addHandler(handler)

    return handler
