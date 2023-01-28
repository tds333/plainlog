# SPDX-FileCopyrightText: 2023 Wolfgang Langner <tds333@mailbox.org>
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
import sys

from ._logger import logger_core


def _default(level=None, extra=None, **kwargs):
    from .processors import DEFAULT_PROCESSORS, DEFAULT_PREPROCESSORS
    from .handlers import DEFAULT_HANDLERS

    logger_core.configure(
        handlers=DEFAULT_HANDLERS,
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
        handlers=[
            {"handler": StreamHandler(stream, SimpleFormatter()), "level": level}
        ],
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

    logger_core.configure(
        handlers=[{"handler": FileHandler(filename), "level": level}],
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
        FileHandler(filename),
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


def _rich(level=None, extra=None, **kwargs):
    from ._rich_handler import RichHandler
    from .processors import (
        add_caller_info,
        Duration,
        DEFAULT_PROCESSORS,
        DEFAULT_PREPROCESSORS,
    )

    preprocessors = (*DEFAULT_PREPROCESSORS, add_caller_info, Duration())
    processors = DEFAULT_PROCESSORS

    logger_core.configure(
        handlers=[
            {
                "handler": RichHandler(
                    rich_tracebacks=True,
                    omit_repeated_times=False,
                    log_time_format="[%H:%M:%S.%f]",
                    tracebacks_show_locals=True,
                    tracebacks_theme="monokai",
                    show_path=True,
                ),
                "level": level,
            }
        ],
        preprocessors=preprocessors,
        processors=processors,
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


def _nothing(level=None, extra=None, **kwargs):
    logger_core.configure(handlers=[], preprocessors=[], processors=[], extra={})


_profiles = {
    "default": _default,
    "develop": _develop,
    "fingerscrossed": _fingerscrossed,
    "simple": _simple,
    "cloud": _cloud,
    "json": _json,
    "file": _file,
    "fingerscrossed_file": _fingerscrossed_file,
    "rich": _rich,
    "console_no_color": _console_no_color,
    "fast": _fast,
    "nothing": _nothing,
}


def configure_log(name=None, level=None, extra=None, **kwargs):
    if name is None:
        name = "default"

    profile = _profiles.get(name)
    if profile is None:
        raise ValueError(f"Name {name!r} is not a valid log profile.")

    profile(level, extra, **kwargs)
