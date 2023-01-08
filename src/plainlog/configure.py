# SPDX-FileCopyrightText: 2023 Wolfgang Langner <tds333@mailbox.org>
#
# SPDX-License-Identifier: Apache-2.0 OR MIT

def configure_log(handlers=None, extra=None, preprocessors=None, processors=None, levels=None):
    from ._logger import logger_core
    from .handlers import DEFAULT_HANDLERS
    from .processors import DEFAULT_PREPROCESSORS, DEFAULT_PROCESSORS

    handlers = DEFAULT_HANDLERS if handlers is None else handlers
    preprocessors = DEFAULT_PREPROCESSORS if preprocessors is None else preprocessors
    processors = DEFAULT_PROCESSORS if processors is None else processors

    logger_core.configure(handlers, extra, preprocessors, processors, levels)


def configure_log_profile(name=None, level=None, **kwargs):
    import sys
    from ._defaults import PLAINLOG_LEVEL
    from ._logger import logger_core
    from .handlers import (
        JsonHandler,
        FileHandler,
        ConsoleHandler,
        StreamHandler,
        FingersCrossedHandler,
    )

    # from .processors import process_exc_info, add_caller_info, Duration

    if level is None:
        level = PLAINLOG_LEVEL
    if name is None:
        name = "default"

    # dynamic parameters with defaults
    stream = kwargs.get("stream", sys.stderr)
    filename = kwargs.get("filename", "plainlog.log")
    action_level = kwargs.get("action_level")
    buffer_size = kwargs.get("buffer_size")
    reset = kwargs.get("reset")

    if name == "default":
        logger_core.configure()
    elif name == "develop":
        from .processors import add_caller_info, Duration, DEFAULT_PROCESSORS, DEFAULT_PREPROCESSORS

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
        )
    elif name == "fingerscrossed":
        from .processors import add_caller_info, Duration, DEFAULT_PROCESSORS, DEFAULT_PREPROCESSORS

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
        )
    elif name == "simple":
        logger_core.configure(
            handlers=[{"handler": StreamHandler(sys.stdout, SimpleFormatter()), "level": level}]
        )
    elif name == "cloud":  # json logging in one line to sys.stdout
        logger_core.configure(handlers=[{"handler": JsonHandler(stream=stream), "level": level}])
    elif name == "json":
        logger_core.configure(
            handlers=[{"handler": JsonHandler(stream=stream, indent=2), "level": level}]
        )
    elif name == "file":
        logger_core.configure(handlers=[{"handler": FileHandler(filename), "level": level}])
    elif name == "fingerscrossed_file":
        fc = FingersCrossedHandler(
            FileHandler(filename),
            action_level=action_level,
            reset=reset,
            buffer_size=buffer_size,
        )
        logger_core.configure(handlers=[{"handler": fc, "level": level}])
    elif name == "rich":
        from ._rich_handler import RichHandler

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
        )
    elif name == "console_no_color":
        logger_core.configure(
            handlers=[
                {
                    "handler": ConsoleHandler(stream, colors=False),
                    "print_errors": True,
                    "level": level,
                }
            ]
        )
    elif name == "fast":
        from .formatters import SimpleFormatter

        logger_core.configure(
            handlers=[
                {
                    "handler": StreamHandler(stream, SimpleFormatter()),
                    "level": level,
                }
            ],
            preprocessors=[],
            processors=[],
        )
    elif name == "nothing":
        logger_core.configure(handlers=[], preprocessors=[], processors=[], extra={}, levels=None)
    else:
        raise ValueError(f"Name {name!r} is not a valid log profile.")

