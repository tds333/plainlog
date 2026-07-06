from time import time

from plainlog._logger import (
    LEVEL_DEBUG,
    logger_core,
    logger_process,
    plainlog_context,
)


def make_record(msg, level=None, name="root", kwargs=None):
    kwargs = {} if kwargs is None else kwargs
    level = LEVEL_DEBUG if level is None else level
    log_record = {
        "level": logger_core.level(level),
        "msg": msg,  # raw message as in std logging
        "message": str(msg),
        "name": name,
        "created": time(),
        "process_id": logger_process.ident,
        "process_name": logger_process.name,
        "context": {**plainlog_context.get({})},
        "extra": {},
        "kwargs": kwargs,
    }

    return log_record
