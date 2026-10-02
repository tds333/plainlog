import sys
from typing import Any, Callable, Dict, Iterable, Optional, Union

from ._base import UniversalProcessorProtocol
from ._logger import logger_core

Processors = Optional[Iterable[UniversalProcessorProtocol]]


def _default(**kwargs: Any) -> Processors:
    from .processors import SimpleFormatter, Stream

    stream = kwargs.get("stream", sys.stdout)
    fmt = kwargs.get("format")

    return [SimpleFormatter(fmt), Stream(stream)]


def _develop(**kwargs: Any) -> Processors:
    from .processors import (
        ConsoleRenderer,
        Stream,
        format_message,
        print_processor_error,
    )

    stream = kwargs.get("stream", sys.stderr)
    processors = [
        format_message,
        ConsoleRenderer(colors=True),
        Stream(stream=stream),
        print_processor_error,
    ]
    return processors


def _fingerscrossed(**kwargs: Any) -> Processors:
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

    processors = [
        format_message,
        ConsoleRenderer(colors=True),
        handler,
        print_processor_error,
    ]

    return processors


def _cloud(**kwargs: Any) -> Processors:
    from .processors import JsonFormatter, Stream

    stream = kwargs.get("stream", sys.stderr)
    return [JsonFormatter(), Stream(stream=stream)]


def _json(**kwargs: Any) -> Processors:
    from .processors import JsonFormatter, Stream

    stream = kwargs.get("stream", sys.stderr)

    return [JsonFormatter(indent=2), Stream(stream=stream)]


def _file(**kwargs: Any) -> Processors:
    from .processors import FileWriter, SimpleFormatter

    filename = kwargs.get("filename", "plainlog.log")
    fmt = kwargs.get("format")
    watch = True

    return [SimpleFormatter(fmt), FileWriter(filename, watch=watch)]


def _fingerscrossed_file(**kwargs: Any) -> Processors:
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
    return [SimpleFormatter(fmt), handler]


def _develop_no_color(**kwargs: Any) -> Processors:
    from .processors import (
        ConsoleRenderer,
        Stream,
        format_message,
        print_processor_error,
    )

    stream = kwargs.get("stream", sys.stderr)

    return [
        format_message,
        ConsoleRenderer(colors=False),
        Stream(stream=stream),
        print_processor_error,
    ]


def _empty(**kwargs: Any) -> Processors:
    return ()


def _no_init(**kwargs: Any) -> Processors:
    return None


def _std_handler(**kwargs: Any) -> Processors:
    from .std import set_as_root_handler

    set_as_root_handler()
    return _default(**kwargs)


def _std_handler_develop(**kwargs: Any) -> Processors:
    from .std import set_as_root_handler

    set_as_root_handler()
    return _develop(**kwargs)


_profiles: Dict[str, Callable[..., Processors]] = {
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


def add_profile(name: str, function: Callable[..., Processors]) -> bool:
    """Register a new logging profile.

    Args:
        name: Profile name (used as key in ``_profiles``).
        function: Callable with signature ``(**kwargs)`` returning an iterable
            of processors, or ``None`` to leave the pipeline unchanged.

    Returns:
        ``True`` if the profile was added, ``False`` if *name* already exists.
    """
    if name in _profiles:
        return False
    _profiles[name] = function

    return True


def configure_log(
    *,
    profile: Optional[str] = None,
    processors: Optional[Iterable[UniversalProcessorProtocol]] = None,
    level: Optional[Union[str, int]] = None,
    close_before_configure: bool = False,
    **kwargs: Any,
) -> None:
    """Configure the global Core and optionally apply a named profile.

    Keyword-only entry point for configuring processors and level; replaces
    the removed per-logger ``configure()`` method.

    Args:
        profile: Optional profile name. When set, the profile function is
            called with *kwargs* and the processors it returns are applied. A
            profile returning ``None`` leaves the pipeline unchanged.
        processors: Explicit processors to install. When both *processors* and
            a *profile* are given, the profile's processors are appended.
        level: Minimum log level.
        close_before_configure: Close the currently registered processors
            before installing the new pipeline. Ignored when nothing is being
            installed (for example a profile that returns ``None``).
        **kwargs: Extra arguments forwarded to the profile function.

    Raises:
        ValueError: If *profile* is not a valid profile name.
    """
    profile_processors: Processors = None
    if profile is not None:
        profile_ = _profiles.get(profile)
        if profile_ is None:
            profile_names = list(_profiles.keys())
            raise ValueError(
                f"Name {profile!r} is not a valid log profile. "
                f"Use one of {profile_names!r}"
            )
        profile_processors = profile_(**kwargs)

    log_processors: Optional[list[UniversalProcessorProtocol]] = None
    if profile_processors is not None:
        log_processors = [*profile_processors]
        if processors is not None:
            log_processors.extend(processors)
    elif processors is not None:
        log_processors = [*processors]
    # if processors is not None:
    #     log_processors = [*processors]
    #     if profile_processors is not None:
    #         log_processors.extend(profile_processors)
    # elif profile_processors is not None:
    #     log_processors = [*profile_processors]

    if close_before_configure and log_processors is not None:
        logger_core.close()
    logger_core.configure(processors=log_processors, level=level)
