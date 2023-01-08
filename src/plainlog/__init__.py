# SPDX-FileCopyrightText: 2023 Wolfgang Langner <tds333@mailbox.org>
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""
The plainlog library provides a pre-instanced logger to facilitate dealing with logging in Python.

Just ``from plainlog import logger``.
"""
import sys
from ._logger import logger
from .configure import configure_log_profile
from . import _defaults

__version__ = "0.1.0"

__all__ = ["logger"]


if _defaults.PLAINLOG_AUTOINIT and sys.stderr:
    configure_log_profile(_defaults.PLAINLOG_PROFILE, _defaults.PLAINLOG_LEVEL)
