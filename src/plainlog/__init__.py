"""
The plainlog library provides a pre-instanced logger to facilitate dealing with logging in Python.

Just ``from plainlog import logger``.
"""

from ._logger import logger  # noqa
from .configure import configure_log  # noqa
from . import _env

__all__ = ["logger", "configure_log"]


configure_log(
    profile=_env.PLAINLOG_PROFILE,
    level=_env.PLAINLOG_LEVEL,
    close_before_configure=True,
)
