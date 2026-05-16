from unittest.mock import patch

from plainlog._base import RecordException
from plainlog._logger import LEVEL_DEBUG, LEVEL_INFO
from plainlog.processors import (
    Duration,
    FilterList,
    WhitelistLevel,
    add_caller_info,
    context_to_extra,
    dynamic_name,
    elapsed,
    eval_extra,
    eval_kwargs,
    eval_lambda,
    filter_all,
    filter_by_level,
    filter_by_name,
    filter_None,
    kwargs_to_extra,
    preformat_message,
    preprocess_exc_info,
    remove_items,
)


def record(msg="test", name="test", level=None, extra=None, kwargs=None):
    level = LEVEL_DEBUG if level is None else level
    return {
        "level": level,
        "msg": msg,
        "message": str(msg),
        "name": name,
        "extra": extra or {},
        "kwargs": kwargs or {},
        "context": {},
    }


class TestAddCallerInfo:
    def test_adds_caller_info(self):
        r = record()
        result = add_caller_info(r, level=1)
        assert "function" in result
        assert result["function"] == "test_adds_caller_info"
        assert "line" in result
        assert "file_name" in result
        assert "file_path" in result
        assert "path" in result
        assert "module" in result
        assert result["module"] == "test_processors"
        assert "process_id" in result
        assert "process_name" in result
        assert "thread_id" in result
        assert "thread_name" in result

    def test_skips_if_function_already_present(self):
        r = record()
        r["function"] = "existing"
        result = add_caller_info(r)
        assert result["function"] == "existing"

    def test_does_not_overwrite_existing_keys(self):
        r = record()
        r["function"] = "custom"
        result = add_caller_info(r)
        assert result["function"] == "custom"


class TestDynamicName:
    def test_sets_name_from_frame(self):
        with patch("plainlog.processors.get_frame") as mock:
            mock.return_value = type(
                "F", (), {"f_globals": {"__name__": "tests.test_processors"}}
            )()
            r = record(name="old")
            result = dynamic_name(r)
            assert result["name"] == "tests.test_processors"

    def test_does_not_set_empty_name(self):
        with patch("plainlog.processors.get_frame") as mock:
            mock.return_value = type("F", (), {"f_globals": {"__name__": ""}})()
            r = record(name="old")
            result = dynamic_name(r)
            assert result["name"] == "old"


class TestEvalKwargs:
    def test_evaluates_callable_kwargs(self):
        r = record(kwargs={"a": lambda: "resolved"})
        result = eval_kwargs(r)
        assert result["kwargs"]["a"] == "resolved"

    def test_empty_kwargs(self):
        r = record()
        result = eval_kwargs(r)
        assert result is r


class TestEvalLambda:
    def test_evaluates_lambda_kwargs(self):
        r = record(kwargs={"a": lambda: "resolved"})
        result = eval_lambda(r)
        assert result["kwargs"]["a"] == "resolved"

    def test_skips_function_kwargs(self):
        def myfunc():
            return "x"

        r = record(kwargs={"a": myfunc})
        result = eval_lambda(r)
        assert result["kwargs"]["a"] is myfunc


class TestEvalExtra:
    def test_evaluates_lambda_extra(self):
        r = record(extra={"a": lambda: "resolved"})
        result = eval_extra(r)
        assert result["extra"]["a"] == "resolved"

    def test_skips_function_extra(self):
        def myfunc():
            return "x"

        r = record(extra={"a": myfunc})
        result = eval_extra(r)
        assert result["extra"]["a"] is myfunc

    def test_empty_extra(self):
        r = record()
        result = eval_extra(r)
        assert result is r


class TestPreprocessExcInfo:
    def test_skips_when_no_exc_info(self):
        r = record()
        result = preprocess_exc_info(r)
        assert "exc_info" not in result
        assert "exception" not in result

    def test_extracts_exc_info_when_true(self):
        r = record(kwargs={"exc_info": True})
        try:
            raise ValueError("boom")
        except ValueError:
            result = preprocess_exc_info(r)
            assert "exc_info" in result
            assert "exception" in result
            exc_type, exc_val, exc_tb = result["exc_info"]
            assert exc_type is ValueError
            assert isinstance(result["exception"], RecordException)

    def test_removes_exc_info_from_kwargs(self):
        r = record(kwargs={"exc_info": True})
        try:
            raise ValueError("x")
        except ValueError:
            result = preprocess_exc_info(r)
            assert "exc_info" not in result["kwargs"]


class TestKwargsToExtra:
    def test_moves_kwargs_to_extra(self):
        r = record(kwargs={"user": "alice", "role": "admin"})
        result = kwargs_to_extra(r)
        assert result["extra"]["user"] == "alice"
        assert result["extra"]["role"] == "admin"

    def test_empty_kwargs(self):
        r = record()
        result = kwargs_to_extra(r)
        assert result is r

    def test_merges_with_existing_extra(self):
        r = record(extra={"existing": 1}, kwargs={"new": 2})
        result = kwargs_to_extra(r)
        assert result["extra"] == {"existing": 1, "new": 2}


class TestContextToExtra:
    def test_moves_context_to_extra(self):
        r = record()
        r["context"] = {"request_id": "abc"}
        result = context_to_extra(r)
        assert result["extra"]["request_id"] == "abc"

    def test_empty_context(self):
        r = record()
        result = context_to_extra(r)
        assert result is r

    def test_merges_with_existing_extra(self):
        r = record(extra={"base": 1})
        r["context"] = {"req": "x"}
        result = context_to_extra(r)
        assert result["extra"] == {"base": 1, "req": "x"}


class TestPreformatMessage:
    def test_skips_preformatted(self):
        r = record(msg="{val}", kwargs={"val": "data"})
        r["preformatted"] = True
        result = preformat_message(r)
        assert result["message"] == "{val}"

    def test_formats_message(self):
        r = record(msg="{val}", kwargs={"val": lambda: "data"})
        result = preformat_message(r)
        assert result["message"] == "data"
        assert result["preformatted"] is True

    def test_no_msg_or_kwargs(self):
        r = record(msg="plain")
        result = preformat_message(r)
        assert result["message"] == "plain"

    def test_format_silently_ignores_errors(self):
        r = record(msg="{missing}", kwargs={"other": "val"})
        result = preformat_message(r)
        assert "missing" in result["message"]


class TestRemoveItems:
    def test_removes_specified_keys(self):
        r = record(name="test")
        r["unwanted"] = 1
        r["also_unwanted"] = 2
        remover = remove_items("unwanted", "also_unwanted")
        result = remover(r)
        assert "unwanted" not in result
        assert "also_unwanted" not in result
        assert result["name"] == "test"

    def test_no_error_when_key_missing(self):
        r = record()
        remover = remove_items("nonexistent")
        result = remover(r)
        assert result is r

    def test_converts_args_to_string(self):
        r = record()
        r[42] = "value"
        remover = remove_items(42)
        result = remover(r)
        assert "42" not in result


class TestFilterNone:
    def test_filters_when_name_is_none(self):
        r = record(name=None)
        assert filter_None(r) == {}

    def test_passes_when_name_not_none(self):
        r = record(name="valid")
        assert filter_None(r) is r


class TestFilterAll:
    def test_filters_all(self):
        assert filter_all(record()) == {}


class TestFilterByName:
    def test_filters_matching_parent(self):
        r = record(name="foo.bar.baz")
        filt = filter_by_name("foo")
        result = filt(r)
        assert result == {}

    def test_passes_non_matching(self):
        r = record(name="other.module")
        filt = filter_by_name("foo")
        result = filt(r)
        assert result is r

    def test_filters_when_name_is_none(self):
        r = record(name=None)
        filt = filter_by_name("foo")
        assert filt(r) == {}


class TestFilterByLevel:
    def test_passes_above_level(self):
        r = record(name="test", level=LEVEL_INFO)
        filt = filter_by_level({"test": 10})
        result = filt(r)
        assert result is r

    def test_filters_below_level(self):
        r = record(name="test", level=LEVEL_DEBUG)
        filt = filter_by_level({"test": 20})
        result = filt(r)
        assert result == {}

    def test_checks_parent_modules(self):
        r = record(name="a.b.c", level=LEVEL_DEBUG)
        filt = filter_by_level({"a": 20})
        result = filt(r)
        assert result == {}

    def test_passes_if_level_is_none(self):
        r = record(name="unconfigured", level=LEVEL_DEBUG)
        filt = filter_by_level({"other": 20})
        result = filt(r)
        assert result is r

    def test_filters_with_false(self):
        r = record(name="blocked", level=LEVEL_DEBUG)
        filt = filter_by_level({"blocked": False})
        result = filt(r)
        assert result == {}

    def test_passes_module_empty_string(self):
        r = record(name="a.b.c", level=LEVEL_DEBUG)
        filt = filter_by_level({"a": 30})
        result = filt(r)
        assert result == {}

    def test_exact_module_name(self):
        r = record(name="mymodule", level=LEVEL_DEBUG)
        filt = filter_by_level({"mymodule": 5})
        result = filt(r)
        assert result is r


class TestFilterList:
    def test_blacklist_filters_out(self):
        fm = FilterList(blacklist=["secret"])
        r = record(name="secret.module")
        assert fm(r) == {}

    def test_whitelist_allows(self):
        fm = FilterList(blacklist=["secret"], whitelist=["allowed"])
        r = record(name="allowed.module")
        assert fm(r) is r

    def test_whitelist_overrides_blacklist(self):
        fm = FilterList(blacklist=["secret"], whitelist=["secret"])
        r = record(name="secret.module")
        assert fm(r) is r

    def test_blacklist_without_whitelist_filters(self):
        fm = FilterList(blacklist=["secret"], whitelist=["public"])
        r = record(name="secret.module")
        assert fm(r) == {}

    def test_no_match_passes(self):
        fm = FilterList(blacklist=["secret"])
        r = record(name="public.module")
        assert fm(r) is r

    def test_partition_caching(self):
        fm = FilterList(blacklist=["a"])
        r1 = record(name="a.b.c")
        r2 = record(name="a.b.c")
        fm(r1)
        cached = fm._partition_cache["a.b.c"]
        fm(r2)
        assert fm._partition_cache["a.b.c"] is cached

    def test_partition(self):
        fm = FilterList(blacklist=["a"])
        parts = fm.partition("a.b.c")
        assert parts == {"a", "a.b", "a.b.c"}


class TestWhitelistLevel:
    def test_filters_non_whitelisted(self):
        wl = WhitelistLevel({"allowed": 10})
        r = record(name="other", level=LEVEL_DEBUG)
        assert wl(r) == {}

    def test_passes_whitelisted_at_level(self):
        wl = WhitelistLevel({"mymod": 10})
        r = record(name="mymod.sub", level=LEVEL_DEBUG)
        assert wl(r) is r

    def test_filters_below_whitelisted_level(self):
        wl = WhitelistLevel({"mymod": 20})
        r = record(name="mymod.sub", level=LEVEL_DEBUG)
        assert wl(r) == {}

    def test_partition_static(self):
        parts = WhitelistLevel.partition("a.b.c")
        assert parts == {"a", "a.b", "a.b.c"}

    def test_partition_cached(self):
        p1 = WhitelistLevel.partition("x.y.z")
        p2 = WhitelistLevel.partition("x.y.z")
        assert p1 is p2


class TestDuration:
    def test_start_records_time(self):
        d = Duration()
        r = record(msg="", kwargs={"start": "task1"})
        result = d(r)
        assert "task1" in d._starts
        assert "task1" in result["message"]

    def test_stop_computes_duration(self):
        d = Duration()
        d._starts["task1"] = 1000.0
        r = record(msg="", kwargs={"stop": "task1"})
        with patch("time.time", return_value=1005.0):
            result = d(r)
        assert "task1" in result["message"]
        assert result["kwargs"]["duration"] == 5.0

    def test_stop_no_start(self):
        d = Duration()
        r = record(kwargs={"stop": "never_started"})
        result = d(r)
        assert "Duration:" not in result.get("message", "")

    def test_start_no_message(self):
        d = Duration(add_message=False)
        r = record(kwargs={"start": "silent"})
        result = d(r)
        assert "silent" in d._starts
        assert result["message"] == "test"

    def test_stop_no_message(self):
        d = Duration(add_message=False)
        d._starts["x"] = 1000.0
        with patch("time.time", return_value=1005.0):
            r = record(kwargs={"stop": "x"})
            result = d(r)
        assert result["kwargs"]["duration"] == 5.0

    def test_no_start_or_stop(self):
        d = Duration()
        r = record()
        result = d(r)
        assert result is r


class TestElapsed:
    def test_adds_elapsed(self):
        r = record()
        result = elapsed(r)
        assert "elapsed" in result
        assert isinstance(result["elapsed"], object)
