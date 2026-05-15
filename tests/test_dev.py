import sys
from datetime import datetime, timezone
from io import StringIO

from plainlog._dev import (
    ConsoleRenderer,
    _ColorfulStyles,
    _pad,
    _PlainStyles,
    default_exception_formatter,
)
from plainlog._logger import LEVEL_DEBUG, LEVEL_INFO


def record(**overrides):
    r = {
        "level": LEVEL_INFO,
        "msg": "test message",
        "message": "test message",
        "name": "test_logger",
        "datetime": datetime(2024, 1, 15, 10, 30, 0, 123456, tzinfo=timezone.utc),
        "extra": {"key1": "val1", "key2": 42},
        "kwargs": {},
        "context": {},
    }
    r.update(overrides)
    return r


def test_pad_pads_to_length():
    assert _pad("hello", 40) == "hello" + " " * 35


def test_pad_no_pad_when_exact():
    assert _pad("1234567890", 10) == "1234567890"


def test_pad_no_pad_when_longer():
    assert _pad("longer than pad", 5) == "longer than pad"


def test_repr_native_str_true():
    r = ConsoleRenderer(repr_native_str=True)
    assert r._repr("hello") == "'hello'"


def test_repr_str_val():
    r = ConsoleRenderer()
    assert r._repr("hello") == "hello"


def test_repr_non_str_val():
    r = ConsoleRenderer()
    assert r._repr(42) == "42"


def test_get_default_level_styles_colors():
    styles = ConsoleRenderer.get_default_level_styles(colors=True)
    assert styles["INFO"] == "\033[34m"
    assert styles["DEBUG"] == "\033[32m"


def test_get_default_level_styles_no_colors():
    styles = ConsoleRenderer.get_default_level_styles(colors=False)
    assert styles["INFO"] == ""
    assert styles["CRITICAL"] == ""


def test_default_exception_formatter_writes_to_sio():
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
    def test_default_uses_colorful_styles(self):
        r = ConsoleRenderer()
        assert r._styles is _ColorfulStyles
        assert r._short_level is True

    def test_plain_styles(self):
        r = ConsoleRenderer(colors=False)
        assert r._styles is _PlainStyles

    def test_custom_level_styles(self):
        r = ConsoleRenderer(level_styles={"INFO": "\033[32m"})
        assert r._level_to_color["INFO"] == "\033[32m\033[1m"

    def test_long_level(self):
        r = ConsoleRenderer(short_level=False)
        assert r._short_level is False
        assert r._longest_level >= len("CRITICAL")

    def test_no_log_name(self):
        r = ConsoleRenderer(log_name=False)
        assert r._log_name is False

    def test_repr_native_str_flag(self):
        r = ConsoleRenderer(repr_native_str=True)
        assert r._repr_native_str is True

    def test_sort_keys_false(self):
        r = ConsoleRenderer(sort_keys=False)
        assert r._sort_keys is False

    def test_custom_exception_formatter(self):
        def custom(sio, exc):
            sio.write("custom")

        r = ConsoleRenderer(exception_formatter=custom)
        assert r._exception_formatter is custom

    def test_basic_output(self):
        r = ConsoleRenderer()
        out = r(record())
        assert "test message" in out
        assert "key1" in out
        assert "val1" in out
        assert "test_logger" in out

    def test_no_timestamp(self):
        r = ConsoleRenderer()
        out = r(record(datetime=None))
        assert "test message" in out

    def test_no_level(self):
        r = ConsoleRenderer()
        out = r(record(level=None))
        assert "test message" in out

    def test_short_level(self):
        r = ConsoleRenderer()
        out = r(record())
        assert "[I]" in out

    def test_long_level_display(self):
        r = ConsoleRenderer(short_level=False)
        out = r(record())
        assert "INFO " in out

    def test_omits_log_name(self):
        r = ConsoleRenderer(log_name=False)
        out = r(record())
        assert "test_logger" not in out

    def test_no_extra(self):
        r = ConsoleRenderer()
        out = r(record(extra={}, kwargs={}, context={}))
        assert "test message" in out

    def test_no_event_padding_without_extra_or_name(self):
        r = ConsoleRenderer()
        out = r(record(extra={}, kwargs={}, context={}, name=None))
        assert out

    def test_sort_keys(self):
        r = ConsoleRenderer(sort_keys=False)
        out = r(record())
        assert "key1" in out

    def test_non_string_event(self):
        r = ConsoleRenderer()
        out = r(record(msg={"a": 1}, message={"a": 1}))
        assert "{'a': 1}" in out

    def test_exc_info_tuple(self):
        r = ConsoleRenderer()
        try:
            raise ValueError("test error")
        except ValueError:
            rec = record(exc_info=sys.exc_info())
            out = r(rec)
        assert "ValueError" in out
        assert "test error" in out

    def test_exc_info_non_tuple(self):
        r = ConsoleRenderer()
        rec = record(exc_info=True)
        out = r(rec)
        assert out

    def test_exception_record(self):
        r = ConsoleRenderer()
        rec = record(exception="RuntimeError: boom")
        out = r(rec)
        assert "RuntimeError" in out

    def test_stack(self):
        r = ConsoleRenderer()
        rec = record(stack="Traceback ...")
        out = r(rec)
        assert "Traceback" in out

    def test_stack_and_exception(self):
        r = ConsoleRenderer()
        rec = record(
            stack="Traceback ...", exc_info=(ValueError, ValueError("x"), None)
        )
        out = r(rec)
        assert "Traceback" in out
        assert "ValueError" in out

    def test_default_exception_formatter_used(self):
        r = ConsoleRenderer()
        try:
            raise Exception("default fmt")
        except Exception:
            rec = record(exc_info=sys.exc_info())
            out = r(rec)
        assert "default fmt" in out

    def test_logger_name_with_extra_pads_event(self):
        r = ConsoleRenderer(pad_event=10)
        rec = record(name="mod", extra={"k": "v"}, kwargs={}, context={})
        out = r(rec)
        assert "test message" in out
        assert "mod" in out
        assert "k" in out

    def test_no_datetime_no_level_no_extra(self):
        r = ConsoleRenderer(short_level=True)
        out = r(
            record(
                datetime=None, level=None, extra={}, kwargs={}, context={}, name=None
            )
        )
        assert "test message" in out
