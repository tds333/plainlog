# SPDX-FileCopyrightText: 2023 Wolfgang Langner <tds333@mailbox.org>
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
import sys

from ._logger import logger_core


def _default(level=None, extra=None, **kwargs):
    from .processors import DEFAULT_PROCESSORS, DEFAULT_PREPROCESSORS
    from .handlers import DefaultHandler

    logger_core.configure(
        handlers=[{"handler": DefaultHandler(), "level": level}],
        preprocessors=DEFAULT_PREPROCESSORS,
        processors=DEFAULT_PROCESSORS,
        extra=extra,
    )


def _develop(level=None, extra=None, **kwargs):
    from .processors import (
        add_caller_info,
        Duration,
        DEFAULT_PROCESSORS,
        DEFAULT_PREPROCESSORS,
    )
    from .handlers import ConsoleHandler

    preprocessors = (*DEFAULT_PREPROCESSORS, add_caller_info, Duration())
    processors = DEFAULT_PROCESSORS
    logger_core.configure(
        handlers=[
            {
                "handler": ConsoleHandler(sys.stderr, colors=True),
                "print_errors": True,
                "level": level,
            }
        ],
        preprocessors=preprocessors,
        processors=processors,
        extra=extra,
    )


def _fingerscrossed(level=None, extra=None, **kwargs):
    from .processors import (
        add_caller_info,
        Duration,
        DEFAULT_PROCESSORS,
        DEFAULT_PREPROCESSORS,
    )
    from .handlers import FingersCrossedHandler, ConsoleHandler

    action_level = kwargs.get("action_level")
    buffer_size = kwargs.get("buffer_size")
    reset = kwargs.get("reset")

    fc = FingersCrossedHandler(
        ConsoleHandler(sys.stderr, colors=True),
        action_level=action_level,
        reset=reset,
        buffer_size=buffer_size,
    )

    preprocessors = (*DEFAULT_PREPROCESSORS, add_caller_info, Duration())
    processors = DEFAULT_PROCESSORS
    logger_core.configure(
        handlers=[
            {
                "handler": fc,
                "print_errors": True,
                "level": level,
            }
        ],
        preprocessors=preprocessors,
        processors=processors,
        extra=extra,
    )


def _simple(level=None, extra=None, **kwargs):
    from .handlers import StreamHandler
    from .formatters import SimpleFormatter
    from .processors import DEFAULT_PROCESSORS, DEFAULT_PREPROCESSORS

    stream = kwargs.get("stream", sys.stderr)
    logger_core.configure(
        handlers=[{"handler": StreamHandler(stream, SimpleFormatter()), "level": level}],
        preprocessors=DEFAULT_PREPROCESSORS,
        processors=DEFAULT_PROCESSORS,
        extra=extra,
    )


def _cloud(level=None, extra=None, **kwargs):
    from .handlers import JsonHandler
    from .processors import DEFAULT_PROCESSORS, DEFAULT_PREPROCESSORS

    stream = kwargs.get("stream", sys.stderr)
    logger_core.configure(
        handlers=[{"handler": JsonHandler(stream=stream), "level": level}],
        preprocessors=DEFAULT_PREPROCESSORS,
        processors=DEFAULT_PROCESSORS,
        extra=extra,
    )


def _json(level=None, extra=None, **kwargs):
    from .handlers import JsonHandler
    from .processors import DEFAULT_PROCESSORS, DEFAULT_PREPROCESSORS

    stream = kwargs.get("stream", sys.stderr)

    logger_core.configure(
        handlers=[{"handler": JsonHandler(stream=stream, indent=2), "level": level}],
        preprocessors=DEFAULT_PREPROCESSORS,
        processors=DEFAULT_PROCESSORS,
        extra=extra,
    )


def _file(level=None, extra=None, **kwargs):
    from .handlers import FileHandler
    from .processors import DEFAULT_PROCESSORS, DEFAULT_PREPROCESSORS

    filename = kwargs.get("filename", "plainlog.log")
    watch = True

    logger_core.configure(
        handlers=[{"handler": FileHandler(filename, watch=watch), "level": level}],
        preprocessors=DEFAULT_PREPROCESSORS,
        processors=DEFAULT_PROCESSORS,
        extra=extra,
    )


def _fingerscrossed_file(level=None, extra=None, **kwargs):
    from .handlers import FingersCrossedHandler, FileHandler
    from .processors import DEFAULT_PROCESSORS, DEFAULT_PREPROCESSORS

    filename = kwargs.get("filename", "plainlog.log")
    action_level = kwargs.get("action_level")
    buffer_size = kwargs.get("buffer_size")
    reset = kwargs.get("reset")

    fc = FingersCrossedHandler(
        FileHandler(filename, watch=True),
        action_level=action_level,
        reset=reset,
        buffer_size=buffer_size,
    )
    logger_core.configure(
        handlers=[{"handler": fc, "level": level}],
        preprocessors=DEFAULT_PREPROCESSORS,
        processors=DEFAULT_PROCESSORS,
        extra=extra,
    )


def _console_no_color(level=None, extra=None, **kwargs):
    from .handlers import ConsoleHandler
    from .processors import DEFAULT_PROCESSORS, DEFAULT_PREPROCESSORS

    stream = kwargs.get("stream", sys.stderr)

    logger_core.configure(
        handlers=[
            {
                "handler": ConsoleHandler(stream, colors=False),
                "print_errors": True,
                "level": level,
            }
        ],
        preprocessors=DEFAULT_PREPROCESSORS,
        processors=DEFAULT_PROCESSORS,
        extra=extra,
    )


def _fast(level=None, extra=None, **kwargs):
    from .handlers import StreamHandler
    from .formatters import SimpleFormatter

    stream = kwargs.get("stream", sys.stderr)

    logger_core.configure(
        handlers=[
            {
                "handler": StreamHandler(stream, SimpleFormatter()),
                "level": level,
            }
        ],
        preprocessors=[],
        processors=[],
        extra=extra,
    )


def _empty(level=None, extra=None, **kwargs):
    logger_core.configure(handlers=[], preprocessors=(), processors=(), extra={})


def _no_init(level=None, extra=None, **kwargs):
    pass


_profiles = {
    "default": _default,
    "develop": _develop,
    "fingerscrossed": _fingerscrossed,
    "simple": _simple,
    "cloud": _cloud,
    "json": _json,
    "file": _file,
    "fingerscrossed_file": _fingerscrossed_file,
    "console_no_color": _console_no_color,
    "fast": _fast,
    "empty": _empty,
    "no_init": _no_init,
}


def add_profile(name, function):
    if name in _profiles:
        return False
    _profiles[name] = function


def configure_log(name=None, level=None, extra=None, **kwargs):
    if name is None:
        name = "default"

    profile = _profiles.get(name)
    if profile is None:
        profile_names = list(_profiles.keys())
        raise ValueError(f"Name {name!r} is not a valid log profile. Use one of {profile_names!r}")

    profile(level, extra, **kwargs)
