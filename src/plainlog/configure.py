import sys

from ._logger import logger


def _default(level=None, **kwargs) -> None:
    from .processors import SimpleFormatter, Stream

    stream = kwargs.get("stream", sys.stdout)
    fmt = kwargs.get("format")

    logger.configure(
        level=level,
        processors=[SimpleFormatter(fmt), Stream(stream)],
    )


def _develop(level=None, **kwargs) -> None:
    from .processors import (
        ConsoleRenderer,
        Stream,
        format_message,
        print_processor_error,
    )

    stream = kwargs.get("stream", sys.stderr)
    logger.configure(
        processors=[
            format_message,
            ConsoleRenderer(colors=True),
            Stream(stream=stream),
            print_processor_error,
        ],
        level=level,
        verbose=True,
    )


def _fingerscrossed(level=None, **kwargs) -> None:
    from .processors import (
        ConsoleRenderer,
        FingersCrossed,
        Stream,
        format_message,
        print_processor_error,
    )

    action_level = kwargs.get("action_level")
    buffer_size = kwargs.get("buffer_size")
    reset = kwargs.get("reset")
    stream = kwargs.get("stream", sys.stderr)

    handler = FingersCrossed(
        Stream(stream),
        action_level=action_level,
        reset=reset,
        buffer_size=buffer_size,
    )

    logger.configure(
        processors=[
            format_message,
            ConsoleRenderer(colors=True),
            handler,
            print_processor_error,
        ],
        level=level,
    )


def _cloud(level=None, **kwargs) -> None:
    from .processors import JsonFormatter, Stream

    stream = kwargs.get("stream", sys.stderr)
    logger.configure(
        level=level,
        processors=[JsonFormatter(), Stream(stream=stream)],
    )


def _json(level=None, **kwargs) -> None:
    from .processors import JsonFormatter, Stream

    stream = kwargs.get("stream", sys.stderr)

    logger.configure(
        level=level,
        processors=[JsonFormatter(indent=2), Stream(stream=stream)],
    )


def _file(level=None, **kwargs) -> None:
    from .processors import FileWriter, SimpleFormatter

    filename = kwargs.get("filename", "plainlog.log")
    fmt = kwargs.get("format")
    watch = True

    logger.configure(
        level=level,
        processors=[SimpleFormatter(fmt), FileWriter(filename, watch=watch)],
    )


def _fingerscrossed_file(level=None, **kwargs) -> None:
    from .processors import FileWriter, FingersCrossed, SimpleFormatter

    filename = kwargs.get("filename", "plainlog.log")
    action_level = kwargs.get("action_level")
    buffer_size = kwargs.get("buffer_size")
    reset = kwargs.get("reset")
    fmt = kwargs.get("format")

    handler = FingersCrossed(
        FileWriter(filename, watch=True),
        action_level=action_level,
        reset=reset,
        buffer_size=buffer_size,
    )
    logger.configure(
        level=level,
        processors=[SimpleFormatter(fmt), handler],
    )


def _develop_no_color(level=None, **kwargs):
    from .processors import (
        ConsoleRenderer,
        Stream,
        format_message,
        print_processor_error,
    )

    stream = kwargs.get("stream", sys.stderr)

    logger.configure(
        level=level,
        processors=[
            format_message,
            ConsoleRenderer(colors=False),
            Stream(stream=stream),
            print_processor_error,
        ],
        verbose=True,
    )


def _empty(level=None, **kwargs):
    logger.configure(processors=(), level=level)


def _no_init(level=None, **kwargs):
    pass


def _std_handler(level=None, **kwargs):
    from .std import set_as_root_handler

    set_as_root_handler()
    _default(level, **kwargs)


def _std_handler_develop(level=None, **kwargs):
    from .std import set_as_root_handler

    set_as_root_handler()
    _develop(level, **kwargs)


_profiles = {
    "default": _default,
    "develop": _develop,
    "develop_no_color": _develop_no_color,
    "cloud": _cloud,
    "json": _json,
    "file": _file,
    "fingerscrossed": _fingerscrossed,
    "fingerscrossed_file": _fingerscrossed_file,
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


def apply_log_profile(name=None, level=None, **kwargs):
    """Configure plainlog with a named profile.

    Available profiles:
        ``"default"``, ``"develop"``, ``"develop_no_color"``, ``"cloud"``,
        ``"json"``, ``"file"``, ``"fingerscrossed"``, ``"fingerscrossed_file"``,
        ``"empty"``, ``"no_init"``, ``"std_handler_default"``,
        ``"std_handler_develop"``

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
