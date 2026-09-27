from __future__ import annotations

import asyncio
import io
import json
import logging
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from plainlog._base import Record, RecordException
from plainlog._logger import LEVEL_DEBUG, LEVEL_ERROR, LEVEL_INFO
from plainlog.processors import (
    AsyncBridge,
    FileWriter,
    FilterList,
    FingersCrossed,
    JsonFormatter,
    SimpleFormatter,
    Stream,
    SubProcessor,
    WhitelistLevel,
    WrapStandardHandler,
    allow_by_name,
    filter_all,
    filter_by_level,
    filter_by_name,
    filter_None,
    format_message,
    print_processor_error,
    redact_by_pattern,
    redact_fields,
)
from tests.helpers import make_record, make_record_with_context

FIXED_CREATED = datetime(
    2026, 9, 20, 11, 15, 41, 123456, tzinfo=timezone.utc
).timestamp()


class BaseHandler:
    def __call__(self, record: Record) -> Any:
        return record


# ---------------------------------------------------------------------------
# Processors
# ---------------------------------------------------------------------------


class TestRedactFields:
    def test_redacts_exact_key(self) -> None:
        r = make_record(username="alice", password="hunter2")
        redactor = redact_fields("password")
        result = redactor(r)
        assert result["password"] == "***REDACTED***"
        assert result["username"] == "alice"

    def test_case_insensitive(self) -> None:
        r = make_record(Password="hunter2")
        redactor = redact_fields("password")
        result = redactor(r)
        assert result["Password"] == "***REDACTED***"

    def test_recurses_into_nested_dicts(self) -> None:
        r = make_record(auth={"password": "hunter2", "user": "alice"})
        redactor = redact_fields("password")
        result = redactor(r)
        assert result["auth"]["password"] == "***REDACTED***"
        assert result["auth"]["user"] == "alice"

    def test_custom_mask(self) -> None:
        r = make_record(password="hunter2")
        redactor = redact_fields("password", mask="<hidden>")
        result = redactor(r)
        assert result["password"] == "<hidden>"

    def test_does_not_match_substring(self) -> None:
        r = make_record(user_password="hunter2")
        redactor = redact_fields("password")
        result = redactor(r)
        assert result["user_password"] == "hunter2"

    def test_recurses_into_deeply_nested_dicts(self) -> None:
        r = make_record(a={"b": {"password": "hunter2"}})
        redactor = redact_fields("password")
        result = redactor(r)
        assert result["a"]["b"]["password"] == "***REDACTED***"

    def test_recurses_into_lists(self) -> None:
        r = make_record(users=[{"password": "hunter2"}, {"user": "alice"}])
        redactor = redact_fields("password")
        result = redactor(r)
        assert result["users"][0]["password"] == "***REDACTED***"
        assert result["users"][1]["user"] == "alice"

    def test_recurses_into_tuples(self) -> None:
        r = make_record(items=({"password": "hunter2"},))
        redactor = redact_fields("password")
        result = redactor(r)
        assert result["items"][0]["password"] == "***REDACTED***"

    def test_matching_container_key_is_not_masked(self) -> None:
        r = make_record(credentials={"user": "alice"})
        redactor = redact_fields("credentials")
        result = redactor(r)
        assert result["credentials"] == {"user": "alice"}

    def test_masks_matching_leaf_inside_matching_container(self) -> None:
        r = make_record(credentials={"password": "hunter2"})
        redactor = redact_fields("credentials", "password")
        result = redactor(r)
        assert result["credentials"]["password"] == "***REDACTED***"

    def test_redacts_multiple_fields(self) -> None:
        r = make_record(password="p", token="t", user="alice")
        redactor = redact_fields("password", "token")
        result = redactor(r)
        assert result["password"] == "***REDACTED***"
        assert result["token"] == "***REDACTED***"
        assert result["user"] == "alice"

    def test_non_string_key_does_not_raise(self) -> None:
        r = make_record(password="hunter2")
        r[42] = "value"
        redactor = redact_fields("password")
        result = redactor(r)
        assert result["password"] == "***REDACTED***"
        assert result[42] == "value"  # type: ignore

    def test_no_args_is_noop(self) -> None:
        r = make_record(password="hunter2")
        redactor = redact_fields()
        result = redactor(r)
        assert result["password"] == "hunter2"

    def test_does_not_mutate_caller_nested_dict(self) -> None:
        caller = {"password": "hunter2"}
        r = make_record(config=caller)
        redactor = redact_fields("password")
        result = redactor(r)
        assert caller == {"password": "hunter2"}
        assert result["config"]["password"] == "***REDACTED***"

    def test_leaves_record_fields_untouched(self) -> None:
        r = make_record(msg="password=hunter2", name="password")
        redactor = redact_fields("password")
        result = redactor(r)
        assert result["msg"] == "password=hunter2"
        assert result["name"] == "password"


class TestRedactByPattern:
    def test_redacts_matching_substring(self) -> None:
        r = make_record(user_password="hunter2", db_password="secret")
        redactor = redact_by_pattern("password")
        result = redactor(r)
        assert result["user_password"] == "***REDACTED***"
        assert result["db_password"] == "***REDACTED***"

    def test_case_insensitive(self) -> None:
        r = make_record(API_KEY="abc123")
        redactor = redact_by_pattern("api_key")
        result = redactor(r)
        assert result["API_KEY"] == "***REDACTED***"

    def test_recurses_into_nested_dicts(self) -> None:
        r = make_record(auth={"api_token": "abc123", "user": "alice"})
        redactor = redact_by_pattern("token")
        result = redactor(r)
        assert result["auth"]["api_token"] == "***REDACTED***"
        assert result["auth"]["user"] == "alice"

    def test_leaves_non_matching_keys(self) -> None:
        r = make_record(username="alice")
        redactor = redact_by_pattern("password", "token", "secret")
        result = redactor(r)
        assert result["username"] == "alice"

    def test_custom_mask(self) -> None:
        r = make_record(secret_key="abc123")
        redactor = redact_by_pattern("secret", mask="<hidden>")
        result = redactor(r)
        assert result["secret_key"] == "<hidden>"

    def test_no_match_returns_equal_record(self) -> None:
        r = make_record()
        redactor = redact_by_pattern("password")
        result = redactor(r)
        assert result == r

    def test_recurses_into_deeply_nested_dicts(self) -> None:
        r = make_record(a={"b": {"password": "hunter2"}})
        redactor = redact_by_pattern("password")
        result = redactor(r)
        assert result["a"]["b"]["password"] == "***REDACTED***"

    def test_recurses_into_lists(self) -> None:
        r = make_record(users=[{"api_token": "t"}, {"user": "alice"}])
        redactor = redact_by_pattern("token")
        result = redactor(r)
        assert result["users"][0]["api_token"] == "***REDACTED***"
        assert result["users"][1]["user"] == "alice"

    def test_recurses_into_tuples(self) -> None:
        r = make_record(items=({"api_token": "t"},))
        redactor = redact_by_pattern("token")
        result = redactor(r)
        assert result["items"][0]["api_token"] == "***REDACTED***"

    def test_matching_container_key_is_not_masked(self) -> None:
        r = make_record(api_key={"value": "secret"})
        redactor = redact_by_pattern("api_key")
        result = redactor(r)
        assert result["api_key"] == {"value": "secret"}

    def test_redacts_multiple_patterns(self) -> None:
        r = make_record(
            user_password="a",
            api_token="b",
            secret_key="c",
            user="d",
        )
        redactor = redact_by_pattern("password", "token", "secret")
        result = redactor(r)
        assert result["user_password"] == "***REDACTED***"
        assert result["api_token"] == "***REDACTED***"
        assert result["secret_key"] == "***REDACTED***"
        assert result["user"] == "d"

    def test_non_string_key_does_not_raise(self) -> None:
        r = make_record(password="hunter2")
        r[42] = "value"
        redactor = redact_by_pattern("password")
        result = redactor(r)
        assert result["password"] == "***REDACTED***"
        assert result[42] == "value"  # type: ignore

    def test_no_args_is_noop(self) -> None:
        r = make_record(password="hunter2")
        redactor = redact_by_pattern()
        result = redactor(r)
        assert result["password"] == "hunter2"

    def test_does_not_mutate_caller_nested_dict(self) -> None:
        caller = {"api_token": "abc123"}
        r = make_record(config=caller)
        redactor = redact_by_pattern("token")
        result = redactor(r)
        assert caller == {"api_token": "abc123"}
        assert result["config"]["api_token"] == "***REDACTED***"


class TestFilterNone:
    def test_filters_when_name_is_none(self) -> None:
        r = make_record(name=None)
        assert filter_None(r) == {}

    def test_passes_when_name_not_none(self) -> None:
        r = make_record(name="valid")
        assert filter_None(r) is r


def test_print_processor_error_prints_and_returns_record(
    capsys: pytest.CaptureFixture[str],
) -> None:
    r = {"processor_error_message": "boom", "processor_error_name_repr": "<proc>"}
    result = print_processor_error(r)
    output = capsys.readouterr().err
    assert result is r
    assert "Got processor <proc> error: boom." in output


def test_print_processor_error_silent_without_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    r = {}
    result = print_processor_error(r)
    assert result is r
    assert capsys.readouterr().err == ""


class TestFilterAll:
    def test_filters_all(self) -> None:
        assert filter_all(make_record()) == {}


class TestFilterByName:
    def test_filters_matching_parent(self) -> None:
        r = make_record(name="foo.bar.baz")
        filt = filter_by_name("foo")
        result = filt(r)
        assert result == {}

    def test_passes_non_matching(self) -> None:
        r = make_record(name="other.module")
        filt = filter_by_name("foo")
        result = filt(r)
        assert result is r

    def test_filters_when_name_is_none(self) -> None:
        r = make_record(name=None)
        filt = filter_by_name("foo")
        assert filt(r) == {}


class TestAllowByName:
    def test_allows_matching_parent(self) -> None:
        r = make_record(name="foo.bar.baz")
        filt = allow_by_name("foo")
        assert filt(r) is r

    def test_drops_non_matching(self) -> None:
        r = make_record(name="other.module")
        filt = allow_by_name("foo")
        assert filt(r) == {}

    def test_drops_when_name_is_none(self) -> None:
        r = make_record(name=None)
        filt = allow_by_name("foo")
        assert filt(r) == {}

    def test_drops_when_name_is_empty(self) -> None:
        r = make_record(name="")
        filt = allow_by_name("foo")
        assert filt(r) == {}


class TestFilterByLevel:
    def test_passes_above_level(self) -> None:
        r = make_record(name="test", level=LEVEL_INFO)
        filt = filter_by_level({"test": 10})
        result = filt(r)
        assert result is r

    def test_filters_below_level(self) -> None:
        r = make_record(name="test", level=LEVEL_DEBUG)
        filt = filter_by_level({"test": 20})
        result = filt(r)
        assert result == {}

    def test_checks_parent_modules(self) -> None:
        r = make_record(name="a.b.c", level=LEVEL_DEBUG)
        filt = filter_by_level({"a": 20})
        result = filt(r)
        assert result == {}

    def test_passes_if_level_is_none(self) -> None:
        r = make_record(name="unconfigured", level=LEVEL_DEBUG)
        filt = filter_by_level({"other": 20})
        result = filt(r)
        assert result is r

    def test_filters_with_false(self) -> None:
        r = make_record(name="blocked", level=LEVEL_DEBUG)
        filt = filter_by_level({"blocked": False})
        result = filt(r)
        assert result == {}

    def test_passes_module_empty_string(self) -> None:
        r = make_record(name="a.b.c", level=LEVEL_DEBUG)
        filt = filter_by_level({"a": 30})
        result = filt(r)
        assert result == {}

    def test_exact_module_name(self) -> None:
        r = make_record(name="mymodule", level=LEVEL_DEBUG)
        filt = filter_by_level({"mymodule": 5})
        result = filt(r)
        assert result is r


class TestFilterList:
    def test_blacklist_filters_out(self) -> None:
        fm = FilterList(blacklist=["secret"])
        r = make_record(name="secret.module")
        assert fm(r) == {}

    def test_whitelist_allows(self) -> None:
        fm = FilterList(blacklist=["secret"], whitelist=["allowed"])
        r = make_record(name="allowed.module")
        assert fm(r) is r

    def test_whitelist_overrides_blacklist(self) -> None:
        fm = FilterList(blacklist=["secret"], whitelist=["secret"])
        r = make_record(name="secret.module")
        assert fm(r) is r

    def test_blacklist_without_whitelist_filters(self) -> None:
        fm = FilterList(blacklist=["secret"], whitelist=["public"])
        r = make_record(name="secret.module")
        assert fm(r) == {}

    def test_no_match_passes(self) -> None:
        fm = FilterList(blacklist=["secret"])
        r = make_record(name="public.module")
        assert fm(r) is r

    def test_partition_caching(self) -> None:
        fm = FilterList(blacklist=["a"])
        r1 = make_record(name="a.b.c")
        r2 = make_record(name="a.b.c")
        fm(r1)
        cached = fm._partition_cache["a.b.c"]
        fm(r2)
        assert fm._partition_cache["a.b.c"] is cached

    def test_partition(self) -> None:
        fm = FilterList(blacklist=["a"])
        parts = fm.partition("a.b.c")
        assert parts == {"a", "a.b", "a.b.c"}


class TestWhitelistLevel:
    def test_filters_non_whitelisted(self) -> None:
        wl = WhitelistLevel({"allowed": 10})
        r = make_record(name="other", level=LEVEL_DEBUG)
        assert wl(r) == {}

    def test_passes_whitelisted_at_level(self) -> None:
        wl = WhitelistLevel({"mymod": 10})
        r = make_record(name="mymod.sub", level=LEVEL_DEBUG)
        assert wl(r) is r

    def test_filters_below_whitelisted_level(self) -> None:
        wl = WhitelistLevel({"mymod": 20})
        r = make_record(name="mymod.sub", level=LEVEL_DEBUG)
        assert wl(r) == {}

    def test_partition_static(self) -> None:
        parts = WhitelistLevel.partition("a.b.c")
        assert parts == {"a", "a.b", "a.b.c"}

    def test_partition_cached(self) -> None:
        p1 = WhitelistLevel.partition("x.y.z")
        p2 = WhitelistLevel.partition("x.y.z")
        assert p1 is p2


class TestSubProcessor:
    def test_default_processors(self) -> None:
        sub = SubProcessor()
        assert sub._processors == ()

    def test_runs_processors_on_copy(self) -> None:
        def add_key(record: Record) -> Any:
            record["added"] = True
            return record

        sub = SubProcessor([add_key])
        r = make_record()
        result = sub(r)
        assert result is not r
        assert result["added"] is True
        assert "added" not in r

    def test_stops_when_processor_drops_record(self) -> None:
        calls = []

        def first(record: Record) -> Any:
            calls.append("first")
            return {}

        def second(record: Record) -> Any:
            calls.append("second")
            return record

        sub = SubProcessor([first, second])
        assert sub(make_record()) == {}
        assert calls == ["first"]

    def test_close_forwards_and_suppresses_errors(self) -> None:
        closed = []

        class Closer:
            def __call__(self, record: Record) -> Any:
                return record

            def close(self) -> None:
                closed.append("closer")

        class BrokenCloser:
            def __call__(self, record: Record) -> Any:
                return record

            def close(self) -> None:
                raise RuntimeError("close failed")

        sub = SubProcessor([Closer(), BrokenCloser()])
        sub.close()
        assert closed == ["closer"]

    def test_preserves_record_exception_through_copy(self) -> None:
        from sys import exc_info

        from plainlog._base import RecordException

        try:
            raise ValueError("bang")
        except ValueError:
            record = {
                "msg": "with exception",
                "message": "with exception",
                "exception": RecordException(*exc_info()),
            }

        captured = []

        def capture(record: Any) -> Any:
            captured.append(record)
            return record

        sub = SubProcessor([capture])
        result = sub(record)

        assert result is not record
        assert result["exception"].type is ValueError
        assert str(result["exception"].value) == "bang"
        assert result["exception"].traceback is not None
        assert "processor_error_message" not in result
        assert "processor_error_name_repr" not in result
        assert captured


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


class TestFormatMessage:
    def test_format_message_simple(self) -> None:
        message = "my message"
        log_record = make_record_with_context(message)
        result = format_message(log_record)
        assert result is log_record
        assert result["message"] == message

    def test_format_message_uses_record_keys(self) -> None:
        log_record = make_record_with_context("my message {user}", user="one")
        result = format_message(log_record)
        assert result["message"] == "my message one"

    def test_format_message_can_use_core_keys(self) -> None:
        log_record = make_record_with_context("logger {name}")
        result = format_message(log_record)
        assert result["message"] == "logger root"

    def test_format_message_keeps_existing(self) -> None:
        log_record = make_record_with_context("ignored {user}", user="x")
        log_record["message"] = "already formatted"
        result = format_message(log_record)
        assert result["message"] == "already formatted"


class TestSimpleFormatter:
    def test_call(self) -> None:
        sf = SimpleFormatter()
        log_record = make_record_with_context("my message")
        result = sf(log_record)
        assert result is log_record
        assert "DEBUG    [root] my message" in result["formatted_message"]

    def test_full_utc_timestamp_without_offset(self) -> None:
        sf = SimpleFormatter()
        log_record = make_record_with_context("my message")
        log_record["created"] = FIXED_CREATED
        result = sf(log_record)

        assert result["formatted_message"].startswith("2026-09-20 11:15:41.123456 ")
        assert "+00:00" not in result["formatted_message"]

    def test_user_key_not_appended_by_default(self) -> None:
        sf = SimpleFormatter()
        log_record = make_record_with_context("my message", user="alice")
        result = sf(log_record)

        assert result["formatted_message"].endswith("my message")
        assert "alice" not in result["formatted_message"]

    def test_no_trailing_space(self) -> None:
        sf = SimpleFormatter()
        log_record = make_record_with_context("my message")
        result = sf(log_record)

        assert result["formatted_message"].endswith("my message")

    def test_custom_format(self) -> None:
        sf = SimpleFormatter("{level_name}: {message}")
        result = sf(make_record_with_context("my message"))

        assert result["formatted_message"] == "DEBUG: my message"

    def test_custom_format_without_user_key(self) -> None:
        sf = SimpleFormatter("{message}")
        result = sf(make_record_with_context("my message"))

        assert result["formatted_message"] == "my message"

    def test_custom_format_includes_user_key(self) -> None:
        sf = SimpleFormatter("{message} {k}")
        result = sf(make_record_with_context("my message", k="v"))

        assert result["formatted_message"] == "my message v"

    def test_interpolates_msg_from_record(self) -> None:
        sf = SimpleFormatter()
        log_record = make_record_with_context("hello {user}", user="bob")
        result = sf(log_record)

        assert "hello bob" in result["formatted_message"]

    def test_evaluates_lambda_in_record(self) -> None:
        sf = SimpleFormatter()
        log_record = make_record_with_context("value {n}", n=lambda: 5)
        result = sf(log_record)

        assert result["formatted_message"].endswith("value 5")


class TestJsonFormatter:
    def test_call(self) -> None:
        f = JsonFormatter()
        record = make_record_with_context("my message")
        result = f(record)
        json_result = json.loads(result["formatted_message"])

        serializable = {
            "message": "my message",
            "name": record["name"],
            "created": record["created"],
            "level_name": record["level_name"],
            "level_no": record["level"],
            "process_id": record["process_id"],
            "process_name": record["process_name"],
        }

        assert json_result == serializable
        assert "extra" not in json_result

    def test_custom_converter(self) -> None:
        f = JsonFormatter(converter=lambda x: "CUSTOM")
        record = make_record_with_context("test")
        record["function"] = object()
        result = json.loads(f(record)["formatted_message"])
        assert result["function"] == "CUSTOM"

    def test_custom_additional_keys(self) -> None:
        f = JsonFormatter(additional_keys=("custom_key",))
        record = make_record_with_context("test")
        record["custom_key"] = "val"
        result = json.loads(f(record)["formatted_message"])
        assert result["custom_key"] == "val"


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


class TestStream:
    def test_init_default_stream(self) -> None:
        h = Stream()
        assert h._stream is sys.stderr

    def test_init_with_stream(self) -> None:
        buf = io.StringIO()
        h = Stream(stream=buf)
        assert h._stream is buf

    def test_repr(self) -> None:
        h = Stream()
        assert "Stream" in repr(h)

    def test_call_writes_to_stream(self) -> None:
        buf = io.StringIO()
        h = Stream(stream=buf)
        record = make_record_with_context("hello")
        h(record)
        assert "hello" in buf.getvalue()

    def test_write_flushable(self) -> None:
        buf = io.StringIO()
        h = Stream(stream=buf)
        h.write("test")
        assert buf.getvalue() == "test\n"

    def test_write_non_flushable(self) -> None:
        class NoFlush:
            def write(self, msg: Any) -> None:
                self._written = msg

        stream = NoFlush()
        h = Stream(stream=stream)  # type: ignore
        h.write("test")
        assert stream._written == "test\n"

    def test_close(self) -> None:
        Stream(sys.stderr).close()

    def test_custom_terminator(self) -> None:
        buf = io.StringIO()
        h = Stream(stream=buf)
        h.terminator = "---\n"
        h.write("hello")
        assert buf.getvalue() == "hello---\n"

    def test_call_returns_record(self) -> None:
        h = Stream()
        record = make_record_with_context()
        assert h(record) is record


class TestWrapStandardHandler:
    def test_init_and_repr(self) -> None:
        std = logging.StreamHandler(sys.stdout)
        h = WrapStandardHandler(std)
        assert "WrapStandardHandler" in repr(h)
        assert "StreamHandler" in repr(h)

    def test_call_returns_record(self) -> None:
        std = logging.StreamHandler(sys.stdout)
        h = WrapStandardHandler(std)
        record = make_record_with_context("wrapped")
        record["file"] = type("F", (), {"path": __file__})()
        record["line"] = 1
        record["function"] = "test_func"
        result = h(record)
        assert result is record

    def test_close(self) -> None:
        std = logging.StreamHandler(sys.stdout)
        h = WrapStandardHandler(std)
        h.close()

    def test_call_with_exception(self, capsys: pytest.CaptureFixture[str]) -> None:
        buf = io.StringIO()
        std = logging.StreamHandler(buf)
        std.setFormatter(logging.Formatter("%(message)s"))
        h = WrapStandardHandler(std)
        record = make_record_with_context("exc")
        record["file"] = type("F", (), {"path": __file__})()
        record["line"] = 2
        record["function"] = "exc_test"
        try:
            raise ValueError("boom")
        except ValueError:
            exc_info = sys.exc_info()
            record["exception"] = RecordException(*exc_info)
        capsys.readouterr()
        h(record)
        err_output = capsys.readouterr().err.split("\n")[0]
        assert "Logging error" in err_output or err_output == ""
        assert h is not None


class TestFingersCrossed:
    def test_init_defaults(self) -> None:
        sub = BaseHandler()
        h = FingersCrossed(sub)
        assert h._level == 40
        assert h._action_triggered is False

    def test_buffers_below_action_level(self) -> None:
        sub = BaseHandler()
        h = FingersCrossed(sub, action_level=40, buffer_size=10)
        record = make_record_with_context("low", LEVEL_DEBUG)
        record["level"] = 10
        h(record)
        assert len(h.buffered_records) == 1
        assert h._action_triggered is False

    def test_triggers_rollover_at_action_level(self) -> None:
        results = []

        class Spy(BaseHandler):
            def __call__(self, record: Record) -> Any:
                results.append(record["msg"])
                return record

        h = FingersCrossed(Spy(), action_level=40, buffer_size=10)
        debug = make_record_with_context("debug", LEVEL_DEBUG)
        debug["level"] = 10
        h(debug)

        error = make_record_with_context("error", LEVEL_ERROR)
        error["level"] = 40
        h(error)

        assert results == ["debug", "error"]
        assert h._action_triggered is True

    def test_direct_after_trigger(self) -> None:
        results = []

        class Spy(BaseHandler):
            def __call__(self, record: Record) -> Any:
                results.append(record["msg"])
                return record

        h = FingersCrossed(Spy(), action_level=40, buffer_size=10)
        d1 = make_record_with_context("first", LEVEL_DEBUG)
        d1["level"] = 10
        h(d1)

        tr = make_record_with_context("trigger", LEVEL_ERROR)
        tr["level"] = 40
        h(tr)

        aft = make_record_with_context("after", LEVEL_DEBUG)
        aft["level"] = 10
        h(aft)

        assert results == ["first", "trigger", "after"]

    def test_repr(self) -> None:
        sub = BaseHandler()
        h = FingersCrossed(sub, action_level=40)
        assert "FingersCrossed" in repr(h)

    def test_close(self) -> None:
        sub = BaseHandler()
        FingersCrossed(sub).close()

    def test_call_returns_record(self) -> None:
        sub = BaseHandler()
        h = FingersCrossed(sub)
        record = make_record_with_context()
        assert h(record) is record

    def test_rollover_empty(self) -> None:
        sub = BaseHandler()
        h = FingersCrossed(sub)
        h.rollover()

    def test_reset(self) -> None:
        results = []

        class Spy(BaseHandler):
            def __call__(self, record: Record) -> Any:
                results.append(record["msg"])
                return record

        h = FingersCrossed(Spy(), action_level=40, reset=True, buffer_size=10)
        d1 = make_record_with_context("d1", LEVEL_DEBUG)
        d1["level"] = 10
        h(d1)

        tr = make_record_with_context("trigger", LEVEL_ERROR)
        tr["level"] = 40
        h(tr)

        assert results == ["d1", "trigger"]

        d2 = make_record_with_context("d2", LEVEL_DEBUG)
        d2["level"] = 10
        h(d2)

        assert results == ["d1", "trigger"]
        assert h._action_triggered is False

    def test_enqueue_after_trigger(self) -> None:
        sub = BaseHandler()
        h = FingersCrossed(sub, action_level=40)
        h._action_triggered = True
        record = make_record_with_context("post", LEVEL_DEBUG)
        record["level"] = 10
        result = h.enqueue(record)
        assert result is False


class TestFileWriter:
    def test_write_to_file(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".log", delete=False) as f:
            path = f.name
        try:
            h = FileWriter(path)
            record = make_record_with_context("file test")
            h(record)
            content = Path(path).read_text(encoding="utf8")
            assert "file test" in content
            h.close()
        finally:
            Path(path).unlink(missing_ok=True)

    def test_delay_creation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "delayed.log"
            h = FileWriter(str(path), delay=True)
            assert not path.exists()
            h(make_record_with_context("now"))
            content = path.read_text(encoding="utf8")
            assert "now" in content
            h.close()

    def test_close_reopens_if_watch(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".log", delete=False) as f:
            path = f.name
        try:
            h = FileWriter(path, watch=True, delay=True)
            h(make_record_with_context("open"))
            assert Path(path).exists()
            h.close()
            assert h._file is None
        finally:
            Path(path).unlink(missing_ok=True)

    def test_reopen_if_needed(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".log", delete=False) as f:
            path = f.name
        try:
            h = FileWriter(path, watch=False)
            h._reopen_if_needed()
            h.close()
        finally:
            Path(path).unlink(missing_ok=True)

    def test_write_recreates_if_closed(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".log", delete=False) as f:
            path = f.name
        try:
            h = FileWriter(path)
            h.close()
            assert h._file is None
            h.write("after close")
            assert h._file is not None
            h.close()
        finally:
            Path(path).unlink(missing_ok=True)

    def test_call_returns_record(self) -> None:
        h = FileWriter("/tmp/nonexistent/test.log", delay=True)
        record = make_record_with_context()
        assert h(record) is record


class TestFileWriterEdgeCases:
    def test_close_twice(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".log", delete=False) as f:
            path = f.name
        try:
            h = FileWriter(path)
            h.close()
            h.close()
        finally:
            Path(path).unlink(missing_ok=True)

    def test_reopen_after_close(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".log", delete=False) as f:
            path = f.name
        try:
            h = FileWriter(path)
            h.close()
            h._reopen_if_needed()
        finally:
            Path(path).unlink(missing_ok=True)

    def test_reopen_if_needed_recreates_deleted_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            real = Path(tmp) / "real.log"
            missing = Path(tmp) / "missing.log"
            h = FileWriter(str(real))
            try:
                assert real.exists()
                h._path = missing
                h._reopen_if_needed()
                assert h._file is not None
                assert missing.exists()
            finally:
                h.close()


class TestAsyncBridge:
    def test_init_and_repr(self) -> None:
        loop = asyncio.new_event_loop()
        try:
            h = AsyncBridge(loop=loop)
            assert "AsyncBridge" in repr(h)
        finally:
            loop.close()

    def test_call_returns_record(self) -> None:
        loop = asyncio.new_event_loop()
        try:
            h = AsyncBridge(loop=loop)
            record = make_record_with_context()
            assert h(record) is record
        finally:
            loop.close()

    def test_call_skips_when_loop_not_running(self) -> None:
        loop = asyncio.new_event_loop()
        try:
            h = AsyncBridge(loop=loop)
            record = make_record_with_context()
            result = h(record)
            assert result is record
        finally:
            loop.close()

    def test_call_with_running_loop(self) -> None:
        async def run() -> None:
            h = AsyncBridge()
            record = make_record_with_context("async")
            result = h(record)
            assert result is record
            assert len(h._futures) == 1

        asyncio.run(run())

    def test_close_with_pending_future(self) -> None:
        from concurrent.futures import Future

        loop = asyncio.new_event_loop()
        try:
            h = AsyncBridge(loop=loop)
            f: Future = Future()
            f.set_result(None)
            h._futures.add(f)
            h.close()
        finally:
            loop.close()

    def test_close_no_future(self) -> None:
        loop = asyncio.new_event_loop()
        try:
            h = AsyncBridge(loop=loop)
            h.close()
        finally:
            loop.close()

    def test_init_no_loop_no_crash(self) -> None:
        # Constructing without a running loop must not raise.
        handler = AsyncBridge()
        assert handler.loop is None

    def test_call_no_loop_skips(self) -> None:
        handler = AsyncBridge()
        record = make_record_with_context()
        result = handler(record)
        assert result is record
        assert handler._futures == set()

    def test_close_flushes_all_futures(self) -> None:
        collected = []

        class CollectingAsyncBridge(AsyncBridge):
            async def write(self, message: Any) -> None:
                collected.append(message)

        loop = asyncio.new_event_loop()

        def run_loop() -> None:
            asyncio.set_event_loop(loop)
            loop.run_forever()

        t = threading.Thread(target=run_loop, daemon=True)
        t.start()
        for _ in range(100):
            if loop.is_running():
                break
            time.sleep(0.001)
        try:
            handler = CollectingAsyncBridge(loop=loop)
            for i in range(5):
                handler(make_record_with_context(f"msg-{i}"))
            handler.close()
            assert len(collected) == 5
            for i in range(5):
                assert any(f"msg-{i}" in c for c in collected)
        finally:
            loop.call_soon_threadsafe(loop.stop)
            t.join(timeout=2)
            loop.close()

    def test_close_with_cancelled_future(self) -> None:
        loop = asyncio.new_event_loop()
        try:
            handler = AsyncBridge(loop=loop)
            future = loop.create_future()
            future.cancel()
            handler._futures.add(future)
            handler.close()
        finally:
            loop.close()

    def test_call_with_done_future(self) -> None:
        collected = []

        class CollectingAsyncBridge(AsyncBridge):
            async def write(self, message: Any) -> None:
                collected.append(message)

        loop = asyncio.new_event_loop()

        def run_loop() -> None:
            asyncio.set_event_loop(loop)
            loop.run_forever()

        t = threading.Thread(target=run_loop, daemon=True)
        t.start()
        for _ in range(100):
            if loop.is_running():
                break
            time.sleep(0.001)
        try:
            handler = CollectingAsyncBridge(loop=loop)
            handler(make_record_with_context("first"))
            # Wait until the first write's future has completed.
            for _ in range(100):
                if any(f.done() for f in handler._futures):
                    break
                time.sleep(0.001)
            # A second call while a done future exists must prune it.
            handler(make_record_with_context("second"))
            handler.close()
            assert len(collected) == 2
        finally:
            loop.call_soon_threadsafe(loop.stop)
            t.join(timeout=2)
            loop.close()

    def test_call_loop_raises_runtimeerror(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class FakeLoop:
            def is_running(self) -> Any:
                return True

        class PlainAsyncBridge(AsyncBridge):
            def write(self, message: Any) -> Any:
                return None

        handler = PlainAsyncBridge(loop=FakeLoop())  # type: ignore
        monkeypatch.setattr(
            asyncio,
            "run_coroutine_threadsafe",
            lambda coro, loop: (_ for _ in ()).throw(RuntimeError("loop not running")),
        )
        record = make_record_with_context()
        result = handler(record)
        assert result is record
        assert handler._futures == set()
