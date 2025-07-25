# SPDX-FileCopyrightText: 2023 Wolfgang Langner <tds333@mailbox.org>
#
# SPDX-License-Identifier: Apache-2.0 OR MIT

"""
Processors useful regardless of the logging framework.
"""

from __future__ import annotations

import contextlib


def eval_lambda_list(data: list) -> list:
    result = []
    for arg in data:
        if callable(arg) and arg.__name__ == "<lambda>":
            with contextlib.suppress(Exception):
                arg_result = arg()
                result.append(arg_result)
        else:
            result.append(arg)

    return result


def eval_lambda_dict(data: dict) -> dict:
    for name, value in data.items():
        if callable(value) and value.__name__ == "<lambda>":
            with contextlib.suppress(Exception):
                result = value()
                data[name] = result

    return data


def eval_list(data: list) -> list:
    result = []
    for arg in data:
        if callable(arg):
            with contextlib.suppress(Exception):
                arg_result = arg()
                result.append(arg_result)
        else:
            result.append(arg)

    return result


def eval_dict(data: dict) -> None:
    for name, value in data.items():
        if callable(value):
            with contextlib.suppress(Exception):
                result = value()
                data[name] = result


def eval_format(msg, args, kwargs) -> str:
    args = eval_lambda_list(args)
    kwargs_ = eval_lambda_dict(kwargs.copy())
    message: str = msg.format(*args, **kwargs_)

    return message
