# SPDX-FileCopyrightText: 2023 Wolfgang Langner <tds333@mailbox.org>
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""
The plainlog library provides a pre-instanced logger to facilitate dealing with logging in Python.

Just ``from plainlog import logger``.
"""

from ._logger import logger, logger_core  # noqa
from .configure import configure_log
from . import _env

__all__ = ["logger"]


configure_log(_env.PLAINLOG_PROFILE, _env.PLAINLOG_LEVEL)
