"""
Processors useful regardless of the logging framework.
"""

from __future__ import annotations

import contextlib
from typing import Any


def eval_lambda_dict(data: dict) -> dict:
    for name, value in data.items():
        if callable(value) and value.__name__ == "<lambda>":
            with contextlib.suppress(Exception):
                result = value()
                data[name] = result

    return data


def eval_dict(data: dict) -> None:
    for name, value in data.items():
        if callable(value):
            with contextlib.suppress(Exception):
                result = value()
                data[name] = result


def eval_format(msg, kwargs: dict) -> str:
    kwargs_ = eval_lambda_dict(kwargs.copy())
    message: str = msg.format(**kwargs_)

    return message


def format_msg(record: dict[str, Any]) -> str:
    msg = record.get("msg", "")
    if not isinstance(msg, str):
        return str(msg)

    try:
        return eval_format(msg, record)
    except (KeyError, IndexError, TypeError, ValueError):
        # Not a format template (e.g. literal braces or a missing field):
        # fall back to the raw message instead of dropping the record.
        return msg


def handle_close(processor):
    if hasattr(processor, "close") and callable(processor.close):
        processor.close()
