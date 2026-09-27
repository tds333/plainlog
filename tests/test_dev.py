from __future__ import annotations

import sys
from io import StringIO
from typing import Any

from plainlog._base import RecordException
from plainlog._dev import (
    ConsoleRenderer,
    _pad,
    _PlainStyles,
    default_exception_formatter,
)
from plainlog._logger import LEVEL_INFO
from tests.helpers import make_record


def test_pad_pads_to_length() -> None:
    assert _pad("hello", 40) == "hello" + " " * 35


def test_pad_no_pad_when_exact() -> None:
    assert _pad("1234567890", 10) == "1234567890"


def test_pad_no_pad_when_longer() -> None:
    assert _pad("longer than pad", 5) == "longer than pad"


def test_repr_native_str_true() -> None:
    r = ConsoleRenderer(repr_native_str=True)
    assert r._repr("hello") == "'hello'"


def test_repr_str_val() -> None:
    r = ConsoleRenderer()
    assert r._repr("hello") == "hello"


def test_repr_non_str_val() -> None:
    r = ConsoleRenderer()
    assert r._repr(42) == "42"


def test_get_default_level_styles_colors() -> None:
    styles = ConsoleRenderer.get_default_level_styles(colors=True)
    assert styles["INFO"] == "\033[34m"
    assert styles["DEBUG"] == "\033[32m"


def test_get_default_level_styles_no_colors() -> None:
    styles = ConsoleRenderer.get_default_level_styles(colors=False)
    assert styles["INFO"] == ""
    assert styles["CRITICAL"] == ""


def test_default_exception_formatter_writes_to_sio() -> None:
    sio = StringIO()
    try:
        raise ValueError("from formatter")
    except ValueError:
        default_exception_formatter(sio, sys.exc_info())
    output = sio.getvalue()
    assert output.startswith("\n")
    assert "ValueError" in output
    assert "from formatter" in output


class TestConsoleRenderer:
    def test_plain_styles(self) -> None:
        r = ConsoleRenderer(colors=False)
        assert r._styles is _PlainStyles

    def test_long_level(self) -> None:
        r = ConsoleRenderer(short_level=False)
        assert r._short_level is False
        assert r._longest_level >= len("CRITICAL")

    def test_no_log_name(self) -> None:
        r = ConsoleRenderer(log_name=False)
        assert r._log_name is False

    def test_repr_native_str_flag(self) -> None:
        r = ConsoleRenderer(repr_native_str=True)
        assert r._repr_native_str is True

    def test_sort_keys_false(self) -> None:
        r = ConsoleRenderer(sort_keys=False)
        assert r._sort_keys is False

    def test_custom_exception_formatter(self) -> None:
        def custom(sio: Any, exc: Any) -> None:
            sio.write("custom")

        r = ConsoleRenderer(exception_formatter=custom)
        assert r._exception_formatter is custom

    def test_basic_output(self) -> None:
        r = ConsoleRenderer()

        out = r(
            make_record(name="test_logger", msg="test message", key1="val1", key2=42)
        )["formatted_message"]
        assert "test message" in out
        assert "key1" in out
        assert "val1" in out
        assert "test_logger" in out

    def test_no_timestamp(self) -> None:
        r = ConsoleRenderer()
        out = r(make_record("test message", name="test_logger", created=None))[
            "formatted_message"
        ]
        assert "test message" in out

    def test_no_level(self) -> None:
        r = ConsoleRenderer()
        out = r(make_record("test message", name="test_logger", level_name=None))[
            "formatted_message"
        ]
        assert "test message" in out

    def test_short_level(self) -> None:
        r = ConsoleRenderer()
        out = r(make_record("test message", name="test_logger", level=LEVEL_INFO))[
            "formatted_message"
        ]
        assert "[I]" in out

    def test_long_level_display(self) -> None:
        r = ConsoleRenderer(short_level=False)
        out = r(make_record("test message", name="test_logger", level=LEVEL_INFO))[
            "formatted_message"
        ]
        assert "INFO " in out

    def test_omits_log_name(self) -> None:
        r = ConsoleRenderer(log_name=False)
        out = r(make_record("test message", name="test_logger"))["formatted_message"]
        assert "test_logger" not in out

    def test_no_extra(self) -> None:
        r = ConsoleRenderer()
        out = r(make_record("test message", name="test_logger"))["formatted_message"]
        assert "test message" in out

    def test_no_event_padding_without_extra_or_name(self) -> None:
        r = ConsoleRenderer()
        out = r(make_record("test message", name=None))["formatted_message"]
        assert out

    def test_sort_keys(self) -> None:
        r = ConsoleRenderer(sort_keys=False)
        out = r(make_record("test message", key1="val1", key2=42))["formatted_message"]
        assert "key1" in out

    def test_non_string_event(self) -> None:
        r = ConsoleRenderer()
        out = r(make_record(msg={"a": 1}))["formatted_message"]
        assert "{'a': 1}" in out

    def test_literal_braces_event(self) -> None:
        r = ConsoleRenderer()
        out = r(make_record(msg="literal {} braces"))["formatted_message"]
        assert "literal {} braces" in out

    def test_exc_info_tuple(self) -> None:
        r = ConsoleRenderer()
        try:
            raise ValueError("test error")
        except ValueError:
            rec = make_record(
                "test message",
                name="test_logger",
                exception=RecordException(*sys.exc_info()),
            )
            out = r(rec)["formatted_message"]
        assert "ValueError" in out
        assert "test error" in out

    def test_exc_info_non_tuple(self) -> None:
        r = ConsoleRenderer()
        rec = make_record(
            "test message",
            name="test_logger",
            exception=RecordException(ValueError, ValueError("x"), None),
        )
        out = r(rec)["formatted_message"]
        assert out
        assert "ValueError" in out

    def test_exception_record(self) -> None:
        r = ConsoleRenderer()
        rec = make_record(
            "test message",
            name="test_logger",
            exception=RecordException(RuntimeError, RuntimeError("boom"), None),
        )
        out = r(rec)["formatted_message"]
        assert "RuntimeError" in out

    def test_stack(self) -> None:
        r = ConsoleRenderer()
        rec = make_record("test message", name="test_logger", stack="Traceback ...")
        out = r(rec)["formatted_message"]
        assert "Traceback" in out

    def test_stack_and_exception(self) -> None:
        r = ConsoleRenderer()
        rec = make_record(
            "test message",
            name="test_logger",
            stack="Traceback ...",
            exception=RecordException(ValueError, ValueError("x"), None),
        )
        out = r(rec)["formatted_message"]
        assert "Traceback" in out
        assert "ValueError" in out

    def test_default_exception_formatter_used(self) -> None:
        r = ConsoleRenderer()
        try:
            raise Exception("default fmt")
        except Exception:
            rec = make_record(
                "test message",
                name="test_logger",
                exception=RecordException(*sys.exc_info()),
            )
            out = r(rec)["formatted_message"]
        assert "default fmt" in out

    def test_logger_name_with_extra_pads_event(self) -> None:
        r = ConsoleRenderer(pad_event=10)
        rec = make_record("test message", name="mod", k="v")
        out = r(rec)["formatted_message"]
        assert "test message" in out
        assert "mod" in out
        assert "k" in out

    def test_no_datetime_no_level_no_extra(self) -> None:
        r = ConsoleRenderer(short_level=True)
        out = r(
            make_record(
                "test message",
                name=None,
                created=None,
                level_name=None,
            )
        )["formatted_message"]
        assert "test message" in out
