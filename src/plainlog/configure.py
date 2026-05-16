# SPDX-FileCopyrightText: 2023 Wolfgang Langner <tds333@mailbox.org>
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
import sys

from ._logger import logger_core


def _default(level=None, **kwargs) -> None:
    from .handlers import DefaultHandler

    logger_core.configure(
        level=level,
        handler=DefaultHandler(),
    )


def _develop(level=None, **kwargs) -> None:
    from .handlers import DevelopHandler

    logger_core.configure(
        handler=DevelopHandler(sys.stderr, colors=True),
        level=level,
        print_errors=True,
    )


def _fingerscrossed(level=None, **kwargs) -> None:
    from .handlers import ConsoleHandler, FingersCrossedHandler

    action_level = kwargs.get("action_level")
    buffer_size = kwargs.get("buffer_size")
    reset = kwargs.get("reset")

    handler = FingersCrossedHandler(
        ConsoleHandler(sys.stderr, colors=True),
        action_level=action_level,
        reset=reset,
        buffer_size=buffer_size,
    )

    logger_core.configure(
        handler=handler,
        level=level,
        print_errors=True,
    )


def _simple(level=None, **kwargs) -> None:
    from .formatters import SimpleFormatter
    from .handlers import StreamHandler

    stream = kwargs.get("stream", sys.stderr)
    handler = StreamHandler(stream, SimpleFormatter())
    logger_core.configure(
        level=level,
        handler=handler,
    )


def _cloud(level=None, **kwargs) -> None:
    from .handlers import JsonHandler

    stream = kwargs.get("stream", sys.stderr)
    handler = JsonHandler(stream=stream)
    logger_core.configure(
        level=level,
        handler=handler,
    )


def _json(level=None, **kwargs) -> None:
    from .handlers import JsonHandler

    stream = kwargs.get("stream", sys.stderr)
    handler = JsonHandler(stream=stream, indent=2)

    logger_core.configure(
        level=level,
        handler=handler,
    )


def _file(level=None, **kwargs) -> None:
    from .handlers import FileHandler

    filename = kwargs.get("filename", "plainlog.log")
    watch = True
    handler = FileHandler(filename, watch=watch)

    logger_core.configure(
        level=level,
        handler=handler,
    )


def _fingerscrossed_file(level=None, **kwargs) -> None:
    from .handlers import FileHandler, FingersCrossedHandler

    filename = kwargs.get("filename", "plainlog.log")
    action_level = kwargs.get("action_level")
    buffer_size = kwargs.get("buffer_size")
    reset = kwargs.get("reset")

    handler = FingersCrossedHandler(
        FileHandler(filename, watch=True),
        action_level=action_level,
        reset=reset,
        buffer_size=buffer_size,
    )
    logger_core.configure(
        level=level,
        handler=handler,
    )


def _console_no_color(level=None, **kwargs):
    from .handlers import ConsoleHandler

    stream = kwargs.get("stream", sys.stderr)

    handler = ConsoleHandler(stream, colors=False)
    logger_core.configure(
        level=level,
        handler=handler,
        print_errors=True,
    )


def _fast(level=None, **kwargs):
    from .formatters import SimpleFormatter
    from .handlers import StreamHandler

    stream = kwargs.get("stream", sys.stderr)
    handler = StreamHandler(stream, SimpleFormatter())

    logger_core.configure(
        handler=handler,
        level=level,
    )


def _empty(level=None, **kwargs):
    logger_core.configure(handler=None, level=level)


def _no_init(level=None, **kwargs):
    pass


def _std_handler(level=None, **kwargs):
    from .std import set_as_root_handler

    set_as_root_handler()
    _default(level, kwargs=kwargs)


def _std_handler_develop(level=None, **kwargs):
    from .std import set_as_root_handler

    set_as_root_handler()
    _develop(level, kwargs=kwargs)


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
    """Register a new logging profile.

    Args:
        name: Profile name (used as key in ``_profiles``).
        function: Callable with signature ``(level, **kwargs)``.

    Returns:
        ``True`` if the profile was added, ``False`` if *name* already exists.
    """
    if name in _profiles:
        return False
    _profiles[name] = function

    return True


def configure_log(name=None, level=None, **kwargs):
    """Configure plainlog with a named profile.

    Available profiles:
        ``"default"``, ``"develop"``, ``"fingerscrossed"``, ``"simple"``,
        ``"cloud"``, ``"json"``, ``"file"``, ``"fingerscrossed_file"``,
        ``"console_no_color"``, ``"fast"``, ``"empty"``, ``"no_init"``,
        ``"std_handler_default"``, ``"std_handler_develop"``

    Args:
        name: Profile name. If ``None``, ``"default"`` is used.
        level: Optional log level to override the profile's default.
        **kwargs: Additional arguments forwarded to the profile function.

    Raises:
        ValueError: If *name* is not a valid profile.
    """
    if name is None:
        name = "default"

    profile = _profiles.get(name)
    if profile is None:
        profile_names = list(_profiles.keys())
        raise ValueError(
            f"Name {name!r} is not a valid log profile. Use one of {profile_names!r}"
        )

    profile(level, **kwargs)


configure_core = logger_core.configure
