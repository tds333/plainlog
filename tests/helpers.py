import logging
from time import time

from plainlog._logger import (
    LEVEL_DEBUG,
    logger_process,
    plainlog_context,
)


def make_record(msg, level=None, name="root", kwargs=None):
    kwargs = {} if kwargs is None else kwargs
    level = LEVEL_DEBUG if level is None else level
    log_record = {
        "level": level,
        "level_name": logging.getLevelName(level),
        "msg": msg,  # raw message as in std logging
        "message": str(msg),
        "name": name,
        "created": time(),
        "process_id": logger_process.ident,
        "process_name": logger_process.name,
        "extra": {**plainlog_context.get({}), **kwargs},
    }

    return log_record
