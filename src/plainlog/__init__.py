# SPDX-FileCopyrightText: 2023 Wolfgang Langner <tds333@mailbox.org>
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""
The plainlog library provides a pre-instanced logger to facilitate dealing with logging in Python.

Just ``from plainlog import logger``.
"""

from ._logger import logger  # noqa
from .configure import apply_log_profile
from . import _env

__all__ = ["logger"]


apply_log_profile(_env.PLAINLOG_PROFILE, _env.PLAINLOG_LEVEL)
