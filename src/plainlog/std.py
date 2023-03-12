# SPDX-FileCopyrightText: 2023 Wolfgang Langner <tds333@mailbox.org>
#
# SPDX-License-Identifier: Apache-2.0 OR MIT

import logging
import contextlib
from datetime import datetime, timezone

from plainlog._logger import logger_core, Options, Logger, get_now_utc, start_time, context


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
        self._core = logger_core
        self._options = Options(name, preprocessors=[], processors=[percent_preformat], extra={})

    _plain_log = Logger._log

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
        # extra = {**extra} if extra is not None else {}
        # extra["exc_info"] = exc_info
        level = self._core.level(level)
        self._plain_log(level, msg, args, kwargs)

    def handle(self, record):
        pass

    def hasHandlers(self):
        return self._core.has_handlers()

    def callHandlers(self, record):
        pass

    def getEffectiveLevel(self):
        return self._core.min_level_no

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
    }

    def emit(self, record):
        core = self._core
        level = core.level(record.levelno)
        level_no, _ = level

        if level_no < core.min_level_no:
            return

        current_datetime = get_now_utc()
        elapsed = current_datetime - start_time

        _, core_preprocessors, __, core_extra = core.options
        kwargs = {}
        extra = {}
        for key, value in record.__dict__.items():
            if key not in self._known_keys:
                extra[key] = value

        #    "elapsed": record.relativeCreated,
        log_record = {
            "elapsed": elapsed,
            "level": level,
            "msg": record.msg,  # raw message as in std logging
            "message": record.getMessage(),
            "name": record.name,
            "datetime": datetime.fromtimestamp(record.created, tz=timezone.utc),
            "process_id": record.process,
            "process_name": record.processName,
            "context": {**context.get()},
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
            "stack_info": record.stack_info,
            "exc_text": record.exc_text,
            "exc_info": record.exc_info,
        }

        stop = False
        for preprocessor in core_preprocessors:
            stop = preprocessor(log_record)
            if stop:
                return

        core.put((log_record, []))
