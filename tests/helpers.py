from __future__ import annotations

import logging
from time import time
from typing import Any

from plainlog._logger import LEVEL_DEBUG


def make_record(
    msg: Any = "test",
    name: str | None = "test",
    level: str | int | None = None,
    **kwargs: Any,
) -> Any:
    from plainlog._logger import logger_process

    level = LEVEL_DEBUG if level is None else level
    return {
        "level": level,
        "level_name": logging.getLevelName(level),  # type: ignore
        "msg": msg,
        "name": name,
        "created": time(),
        "process_id": logger_process.ident,
        "process_name": logger_process.name,
        **kwargs,
    }


def make_record_with_context(
    msg: Any = "test",
    level: str | int | None = None,
    name: str = "root",
    **kwargs: Any,
) -> Any:
    from plainlog._logger import logger_process, plainlog_context

    level = LEVEL_DEBUG if level is None else level
    return {
        "level": level,
        "level_name": logging.getLevelName(level),  # type: ignore
        "msg": msg,
        "name": name,
        "created": time(),
        "process_id": logger_process.ident,
        "process_name": logger_process.name,
        **plainlog_context.get({}),
        **kwargs,
    }
