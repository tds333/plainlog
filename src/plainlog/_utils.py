"""
Processors useful regardless of the logging framework.
"""

from __future__ import annotations

import contextlib
from typing import Any, Dict


def eval_lambda_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    ret = {}
    for name, value in data.items():
        if callable(value) and value.__name__ == "<lambda>":
            with contextlib.suppress(Exception):
                result = value()
                ret[name] = result
        else:
            ret[name] = value

    return ret


def format_msg(record: Dict[str, Any]) -> str:
    msg = record.get("msg", "")
    if not isinstance(msg, str):
        return str(msg)

    try:
        return msg.format(**record)
    except (KeyError, IndexError, TypeError, ValueError):
        # Not a format template (e.g. literal braces or a missing field):
        # fall back to the raw message instead of dropping the record.
        return msg


def handle_close(processor: Any) -> None:
    if hasattr(processor, "close") and callable(processor.close):
        processor.close()
