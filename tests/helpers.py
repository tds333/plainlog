import logging
from time import time

from plainlog._logger import LEVEL_DEBUG


def make_record(msg="test", name="test", level=None, **kwargs):
    from plainlog._logger import logger_process

    level = LEVEL_DEBUG if level is None else level
    return {
        "level": level,
        "level_name": logging.getLevelName(level),
        "msg": msg,
        "name": name,
        "created": time(),
        "process_id": logger_process.ident,
        "process_name": logger_process.name,
        **kwargs,
    }


def make_record_with_context(msg="test", level=None, name="root", **kwargs):
    from plainlog._logger import logger_process, plainlog_context

    level = LEVEL_DEBUG if level is None else level
    return {
        "level": level,
        "level_name": logging.getLevelName(level),
        "msg": msg,
        "name": name,
        "created": time(),
        "process_id": logger_process.ident,
        "process_name": logger_process.name,
        **plainlog_context.get({}),
        **kwargs,
    }
