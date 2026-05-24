# SPDX-FileCopyrightText: 2023 Wolfgang Langner <tds333@mailbox.org>
#
# SPDX-License-Identifier: Apache-2.0 OR MIT

"""
Processors useful regardless of the logging framework.
"""

from __future__ import annotations

import contextlib


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


def eval_format(msg, kwargs) -> str:
    kwargs_ = eval_lambda_dict(kwargs.copy())
    message: str = msg.format(**kwargs_)

    return message


def get_processed_extra(record: dict) -> dict:
    extra = record.get("extra", {})
    kwargs = record.get("kwargs", {})
    context = record.get("context", {})
    if not extra and not kwargs and not context:
        return {}
    extra = {**extra, **context, **kwargs}
    extra = eval_lambda_dict(extra)

    return extra
