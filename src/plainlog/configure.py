# SPDX-FileCopyrightText: 2023 Wolfgang Langner <tds333@mailbox.org>
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
import sys

from ._logger import logger_core


def _default(level=None, extra=None, **kwargs) -> None:
    from .handlers import DefaultHandler, ProcessingHandler
    from .processors import DEFAULT_PROCESSORS

    handler = ProcessingHandler(None, DEFAULT_PROCESSORS, DefaultHandler())

    logger_core.configure(
        level=level,
        handler=handler,
        extra=extra,
    )


def _develop(level=None, extra=None, **kwargs) -> None:
    from .handlers import ConsoleHandler, ProcessingHandler
    from .processors import (
        DEFAULT_PROCESSORS,
        Duration,
        add_caller_info,
    )

    preprocessors = (add_caller_info, Duration())
    # processors = DEFAULT_PROCESSORS

    handler = ProcessingHandler(
        preprocessors, handler=ConsoleHandler(sys.stderr, colors=True)
    )

    logger_core.configure(
        handler=handler,
        extra=extra,
        level=level,
        print_errors=True,
    )


def _fingerscrossed(level=None, extra=None, **kwargs) -> None:
    from .handlers import ConsoleHandler, FingersCrossedHandler, ProcessingHandler
    from .processors import (
        Duration,
        add_caller_info,
    )

    action_level = kwargs.get("action_level")
    buffer_size = kwargs.get("buffer_size")
    reset = kwargs.get("reset")

    fc = FingersCrossedHandler(
        ConsoleHandler(sys.stderr, colors=True),
        action_level=action_level,
        reset=reset,
        buffer_size=buffer_size,
    )

    preprocessors = (add_caller_info, Duration())
    # processors = (*DEFAULT_PROCESSORS)
    handler = ProcessingHandler(preprocessors, handler=fc)
    logger_core.configure(
        handler=handler,
        extra=extra,
        level=level,
        print_errors=True,
    )


def _simple(level=None, extra=None, **kwargs) -> None:
    from .formatters import SimpleFormatter
    from .handlers import StreamHandler, ProcessingHandler
    from .processors import DEFAULT_PREPROCESSORS, DEFAULT_PROCESSORS

    stream = kwargs.get("stream", sys.stderr)
    preprocessors = DEFAULT_PREPROCESSORS
    processors = (*DEFAULT_PROCESSORS, StreamHandler(stream, SimpleFormatter()))
    handler = ProcessingHandler(preprocessors, processors)
    logger_core.configure(
        extra=extra,
        level=level,
        handler=handler,
    )


def _cloud(level=None, extra=None, **kwargs) -> None:
    from .handlers import JsonHandler, ProcessingHandler
    from .processors import DEFAULT_PREPROCESSORS, DEFAULT_PROCESSORS

    stream = kwargs.get("stream", sys.stderr)
    preprocessors = (DEFAULT_PREPROCESSORS,)
    processors = (*DEFAULT_PROCESSORS, JsonHandler(stream=stream))
    handler = ProcessingHandler(preprocessors, processors)
    logger_core.configure(
        extra=extra,
        level=level,
        handler=handler,
    )


def _json(level=None, extra=None, **kwargs) -> None:
    from .handlers import JsonHandler, ProcessingHandler
    from .processors import DEFAULT_PREPROCESSORS, DEFAULT_PROCESSORS

    stream = kwargs.get("stream", sys.stderr)
    preprocessors = (DEFAULT_PREPROCESSORS,)
    processors = (*DEFAULT_PROCESSORS, JsonHandler(stream=stream, indent=2))
    handler = ProcessingHandler(preprocessors, processors)

    logger_core.configure(
        extra=extra,
        level=level,
        handler=handler,
    )


def _file(level=None, extra=None, **kwargs) -> None:
    from .handlers import FileHandler, ProcessingHandler
    from .processors import DEFAULT_PREPROCESSORS, DEFAULT_PROCESSORS

    filename = kwargs.get("filename", "plainlog.log")
    watch = True
    preprocessors = (DEFAULT_PREPROCESSORS,)
    processors = (*DEFAULT_PROCESSORS, FileHandler(filename, watch=watch))
    handler = ProcessingHandler(preprocessors, processors)

    logger_core.configure(
        extra=extra,
        level=level,
        handler=handler,
    )


def _fingerscrossed_file(level=None, extra=None, **kwargs) -> None:
    from .handlers import FileHandler, FingersCrossedHandler, ProcessingHandler
    from .processors import DEFAULT_PREPROCESSORS, DEFAULT_PROCESSORS

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
    preprocessors = (DEFAULT_PREPROCESSORS,)
    processors = (*DEFAULT_PROCESSORS, fc)
    handler = ProcessingHandler(preprocessors, processors)
    logger_core.configure(
        extra=extra,
        level=level,
        handler=handler,
    )


def _console_no_color(level=None, extra=None, **kwargs):
    from .handlers import ConsoleHandler, ProcessingHandler
    from .processors import DEFAULT_PREPROCESSORS, DEFAULT_PROCESSORS

    stream = kwargs.get("stream", sys.stderr)

    preprocessors = (DEFAULT_PREPROCESSORS,)
    processors = (*DEFAULT_PROCESSORS, ConsoleHandler(stream, colors=False))
    handler = ProcessingHandler(preprocessors, processors)
    logger_core.configure(
        extra=extra,
        level=level,
        handler=handler,
        print_errors=True,
    )


def _fast(level=None, extra=None, **kwargs):
    from .formatters import SimpleFormatter
    from .handlers import StreamHandler, ProcessingHandler

    stream = kwargs.get("stream", sys.stderr)
    preprocessors = []
    processors = [StreamHandler(stream, SimpleFormatter())]
    handler = ProcessingHandler(preprocessors, processors)

    logger_core.configure(
        handler=handler,
        extra=extra,
        level=level,
    )


def _empty(level=None, extra=None, **kwargs):
    logger_core.configure(extra={}, level=level)


def _no_init(level=None, extra=None, **kwargs):
    pass


def _std_handler(level=None, extra=None, **kwargs):
    from .std import set_as_root_handler

    set_as_root_handler()
    _default(level, extra, kwargs=kwargs)


def _std_handler_develop(level=None, extra=None, **kwargs):
    from .std import set_as_root_handler

    set_as_root_handler()
    _develop(level, extra, kwargs=kwargs)


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
    "std_handler_default": _std_handler,
    "std_handler_develop": _std_handler_develop,
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
        raise ValueError(
            f"Name {name!r} is not a valid log profile. Use one of {profile_names!r}"
        )

    profile(level, extra, **kwargs)


configure_core = logger_core.configure
