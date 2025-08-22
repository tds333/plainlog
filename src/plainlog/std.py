# SPDX-FileCopyrightText: 2023 Wolfgang Langner <tds333@mailbox.org>
#
# SPDX-License-Identifier: Apache-2.0 OR MIT

import contextlib
import logging
from datetime import datetime, timezone

from ._logger import logger_core, plainlog_context, logger


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
        level = core.level(record.levelno)
        level_no, _ = level

        if level_no < core.min_level_no:
            return

        _, core_preprocessors, __, core_extra = core.options
        kwargs: dict = {}
        extra: dict = {}
        for key, value in record.__dict__.items():
            if key not in self._known_keys:
                extra[key] = value

        log_record = {
            "level": level,
            "msg": record.msg,  # raw message as in std logging
            "message": record.getMessage(),
            "name": record.name,
            "datetime": datetime.fromtimestamp(record.created, tz=timezone.utc),
            "process_id": record.process,
            "process_name": record.processName,
            "context": {**plainlog_context.get({})},
            "extra": {**core_extra, **extra},
            "args": record.args,
            "kwargs": kwargs,
            "preformatted": True,
            "function": record.funcName,
            "line": record.lineno,
            "module": record.module,
            "path": record.pathname,
            "thread_id": record.thread,
            "thread_name": record.threadName,
            # "task_name": record.taskName, # since Python 3.12
            "stack_info": record.stack_info,
            "exc_text": record.exc_text,
            "exc_info": record.exc_info,
        }

        stop = False
        for preprocessor in core_preprocessors:
            stop = preprocessor(log_record)
            if stop:
                return

        core.log(log_record, processors=())


def set_as_root_handler() -> None:
    root = logging.getLogger(name="root")
    root.addHandler(StdInterceptHandler())
