# SPDX-FileCopyrightText: 2023 Wolfgang Langner <tds333@mailbox.org>
#
# SPDX-License-Identifier: Apache-2.0 OR MIT

# Mostly copied from structlog.

from __future__ import annotations
import traceback
import sys

from io import StringIO
from typing import Any, Iterable, TextIO, Type, Union

from ._frames import _format_exception
from .formatters import format_message

from typing import Protocol


__all__ = [
    "ConsoleRenderer",
]

_IS_WINDOWS = sys.platform == "win32"

_EVENT_WIDTH = 40  # pad the event name to so many characters


def _pad(s: str, length: int) -> str:
    """
    Pads *s* to length *length*.
    """
    missing = length - len(s)

    return s + " " * (missing if missing > 0 else 0)


RESET_ALL = "\033[0m"
BRIGHT = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
BLUE = "\033[34m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
YELLOW = "\033[33m"
GREEN = "\033[32m"
RED_BACK = "\033[41m"


if _IS_WINDOWS:  # pragma: no cover
    _use_colors = False
else:
    # On other OSes, use colors by default.
    _use_colors = True


class _Styles(Protocol):
    reset: str
    bright: str
    level_critical: str
    level_error: str
    level_warn: str
    level_info: str
    level_debug: str
    level_notset: str

    timestamp: str
    logger_name: str
    kv_key: str
    kv_value: str


Styles = Union[_Styles, Type[_Styles]]


class _ColorfulStyles:
    reset = RESET_ALL
    bright = BRIGHT

    level_critical = RED
    level_error = RED
    level_warn = YELLOW
    level_info = BLUE
    level_debug = GREEN
    level_notset = RED_BACK

    timestamp = DIM
    logger_name = BLUE
    # logger_name = DIM
    kv_key = CYAN
    kv_value = MAGENTA


class _PlainStyles:
    reset = ""
    bright = ""

    level_critical = ""
    # level_exception = ""
    level_error = ""
    level_warn = ""
    level_info = ""
    level_debug = ""
    level_notset = ""

    timestamp = ""
    logger_name = ""
    kv_key = ""
    kv_value = ""


def default_exception_formatter(sio: TextIO, exc_info) -> None:
    # sio.write("\n" + _format_exception(exc_info))
    sio.write("\n")
    traceback.print_exception(exc_info[0], exc_info[1], exc_info[2], None, sio)


class ConsoleRenderer:
    def __init__(
        self,
        pad_event: int = _EVENT_WIDTH,
        colors: bool = _use_colors,
        force_colors: bool = False,
        repr_native_str: bool = False,
        level_styles: Styles | None = None,
        exception_formatter=default_exception_formatter,
        sort_keys: bool = True,
        short_level: bool = True,
        log_name: bool = True,
    ):
        styles: Styles
        if colors:
            styles = _ColorfulStyles
        else:
            styles = _PlainStyles

        self._styles = styles
        self._pad_event = pad_event

        if level_styles is None:
            self._level_to_color: dict = self.get_default_level_styles(colors)
        else:
            self._level_to_color: dict = level_styles

        for key in self._level_to_color.keys():
            self._level_to_color[key] += styles.bright
        self._longest_level = len(max(self._level_to_color.keys(), key=lambda e: len(e)))

        self._repr_native_str = repr_native_str
        self._exception_formatter = exception_formatter
        self._sort_keys = sort_keys
        self._shoert_level = short_level
        self._log_name = log_name

    def _repr(self, val: Any) -> str:
        """
        Determine representation of *val* depending on its type &
        self._repr_native_str.
        """
        if self._repr_native_str is True:
            return repr(val)

        if isinstance(val, str):
            return val
        else:
            return repr(val)

    def __call__(self, record) -> str:
        sio = StringIO()

        ts = record.get("datetime", None)
        if ts is not None:
            sio.write(
                # can be a number if timestamp is UNIXy
                self._styles.timestamp + ts.astimezone().strftime("%H:%M:%S.%f") + self._styles.reset + " "
            )
        level = record.get("level", None)
        if level is not None:
            if self._shoert_level:
                level = level.name
                sio.write(self._level_to_color.get(level, "") + "[" + level[0] + "] " + self._styles.reset)
            else:
                level = level.name
                sio.write(
                    self._level_to_color.get(level, "") + _pad(level, self._longest_level + 1) + self._styles.reset
                )

        event = format_message(record)
        if not isinstance(event, str):
            event = str(event)

        extra = record.get("extra")
        logger_name = record.get("name", None)
        if not self._log_name:
            logger_name = None
        if extra or logger_name:
            event = _pad(event, self._pad_event) + self._styles.reset + " "
        else:
            event += self._styles.reset
        # sio.write(self._styles.bright + event)
        sio.write(event)

        if logger_name is not None:
            sio.write(
                "["
                + self._styles.logger_name
                # + self._styles.bright
                + logger_name
                + self._styles.reset
                + "] "
            )

        stack = record.get("stack", None)
        exc = record.get("exception", None)
        exc_info = record.get("exc_info", None)

        extra_dict_keys: Iterable[str] = extra.keys()
        if self._sort_keys:
            extra_dict_keys = sorted(extra_dict_keys)

        sio.write(
            " ".join(
                self._styles.kv_key
                + key
                + self._styles.reset
                + "="
                + self._styles.kv_value
                + self._repr(extra[key])
                + self._styles.reset
                for key in extra_dict_keys
            )
        )

        if stack is not None:
            sio.write("\n" + stack)
            if exc_info or exc is not None:
                sio.write("\n\n" + "=" * 79 + "\n")

        if exc_info:
            if not isinstance(exc_info, tuple):
                exc_info = sys.exc_info()

            self._exception_formatter(sio, exc_info)
        elif exc is not None:
            sio.write("\n" + exc)
        # sio.write("\n")

        return sio.getvalue()

    @staticmethod
    def get_default_level_styles(colors: bool = True) -> dict:
        """
        Get the default styles for log levels
        """
        styles: Styles
        if colors:
            styles = _ColorfulStyles
        else:
            styles = _PlainStyles
        return {
            "CRITICAL": styles.level_critical,
            "ERROR": styles.level_error,
            "WARNING": styles.level_warn,
            "INFO": styles.level_info,
            "DEBUG": styles.level_debug,
            "NOTSET": styles.level_notset,
        }
