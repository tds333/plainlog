# SPDX-FileCopyrightText: 2023 Wolfgang Langner <tds333@mailbox.org>
#
# SPDX-License-Identifier: Apache-2.0 OR MIT

import contextlib
import logging
from datetime import datetime, timezone

from ._logger import logger_core, plainlog_context, logger


def percent_preformat(record):
    preformatted = record.get("preformatted", False)
    if preformatted:
        return

    msg = record.get("msg", "")
    args = record.get("args", [])
    if msg and args:
        with contextlib.suppress(Exception):
            record["message"] = msg % args
            record["preformatted"] = True


class PlainlogStdLogger(logging.Logger):
    def __init__(self, name, level=logging.NOTSET):
        super().__init__(name, level)
        self._plain_logger = logger.new(name, (), (percent_preformat,), {})

    def setLevel(self, level):
        pass

    def debug(self, msg, *args, **kwargs):
        self._log(logging.DEBUG, msg, args, kwargs)

    def info(self, msg, *args, **kwargs):
        self._log(logging.INFO, msg, args, kwargs)

    def warning(self, msg, *args, **kwargs):
        self._log(logging.WARNING, msg, args, kwargs)

    def warn(self, msg, *args, **kwargs):
        self.warning(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self._log(logging.ERROR, msg, args, kwargs)

    def exception(self, msg, *args, exc_info=True, **kwargs):
        self.error(msg, *args, exc_info=exc_info, **kwargs)

    def critical(self, msg, *args, **kwargs):
        self._log(logging.CRITICAL, msg, args, kwargs)

    def fatal(self, msg, *args, **kwargs):
        self.critical(msg, *args, **kwargs)

    def log(self, level, msg, *args, **kwargs):
        if not isinstance(level, int):
            if logging.raiseExceptions:
                raise TypeError("level must be an integer")
            else:
                return
        self._log(level, msg, args, kwargs)

    def _log(self, level, msg, args, kwargs):
        self._plain_logger.log(level, msg, args, kwargs)

    def handle(self, record):
        pass

    def hasHandlers(self):
        return self._plain_logger._core.has_handlers()

    def callHandlers(self, record):
        pass

    def getEffectiveLevel(self):
        return self._plain_log._core.min_level_no

    def isEnabledFor(self, level):
        if self.disabled:
            return False

        if level >= self.getEffectiveLevel():
            return True

        return False


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

    def emit(self, record):
        core = self._core
        level = core.level(record.levelno)
        level_no, _ = level

        if level_no < core.min_level_no:
            return

        _, core_preprocessors, __, core_extra = core.options
        kwargs = {}
        extra = {}
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


def set_as_std_logger_class():
    logging.setLoggerClass(PlainlogStdLogger)


def set_as_root_handler():
    root = logging.getLogger(name="root")
    root.addHandler(StdInterceptHandler())
