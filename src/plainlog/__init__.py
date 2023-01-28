# SPDX-FileCopyrightText: 2023 Wolfgang Langner <tds333@mailbox.org>
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""
The plainlog library provides a pre-instanced logger to facilitate dealing with logging in Python.

Just ``from plainlog import logger``.
"""
from ._logger import Logger, logger_core
from .configure import configure_log
from . import _defaults
from .processors import DEFAULT_LOGGER_PREPROCESSORS, DEFAULT_LOGGER_PROCESSORS

__version__ = "0.1.0"

__all__ = ["logger", "logger_core", "configure_log"]


if _defaults.PLAINLOG_AUTOINIT:
    configure_log(_defaults.PLAINLOG_PROFILE, _defaults.PLAINLOG_LEVEL)

logger = Logger(
    core=logger_core,
    name="root",
    preprocessors=DEFAULT_LOGGER_PREPROCESSORS,
    processors=DEFAULT_LOGGER_PROCESSORS,
    extra={},
)
