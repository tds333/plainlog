from plainlog._logger import logger_core, LEVEL_DEBUG, logger_process, plainlog_context, get_now_utc
from plainlog._recattrs import Level, HandlerRecord, Options


def make_record(msg, level=None, *args, **kwargs):
    level = LEVEL_DEBUG if level is None else level
    log_record = {
        "level": logger_core.level(level),
        "msg": msg,  # raw message as in std logging
        "message": str(msg),
        "name": "root",
        "datetime": get_now_utc(),
        "process_id": logger_process.ident,
        "process_name": logger_process.name,
        "context": {**plainlog_context.get({})},
        "extra": {},
        "args": args,
        "kwargs": kwargs,
    }

    return log_record
