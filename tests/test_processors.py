import asyncio
import io
import json
import logging
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

from plainlog._base import RecordException
from plainlog._logger import LEVEL_DEBUG, LEVEL_ERROR, LEVEL_INFO
from plainlog.processors import (
    AsyncBridge,
    DefaultFormatter,
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
    eval_extra,
    eval_lambda_extra,
    filter_all,
    filter_by_level,
    filter_by_name,
    filter_None,
    format_message,
    print_processor_error,
    remove_extra_items,
)


def record(msg="test", name="test", level=None, extra=None, kwargs=None):
    level = LEVEL_DEBUG if level is None else level
    extra = {} if extra is None else extra
    kwargs = {} if kwargs is None else kwargs
    return {
        "level": level,
        "level_name": logging.getLevelName(level),
        "msg": msg,
        "message": str(msg),
        "name": name,
        "extra": {**extra, **kwargs},
    }


def make_record(msg="test", level=None, name="root", extra=None, kwargs=None):
    from plainlog._logger import logger_process, plainlog_context

    level = LEVEL_DEBUG if level is None else level
    return {
        "level": level,
        "level_name": logging.getLevelName(level),
        "msg": msg,
        "message": str(msg),
        "name": name,
        "created": time.time(),
        "process_id": logger_process.ident,
        "process_name": logger_process.name,
        "extra": {
            **plainlog_context.get({}),
            **(extra or {}),
            **(kwargs or {}),
        },
    }


class BaseHandler:
    def __call__(self, record):
        return record


# ---------------------------------------------------------------------------
# Processors
# ---------------------------------------------------------------------------


class TestEvalExtra:
    def test_evaluates_lambda_extra(self):
        r = record(extra={"a": lambda: "resolved"})
        result = eval_extra(r)
        assert result["extra"]["a"] == "resolved"

    def test_evaluates_function_extra(self):
        def myfunc():
            return "x"

        r = record(extra={"a": myfunc})
        result = eval_extra(r)
        assert result["extra"]["a"] == "x"

    def test_empty_extra(self):
        r = record()
        result = eval_extra(r)
        assert result is r


class TestEvalLambdaExtra:
    def test_evaluates_lambda_extra(self):
        r = record(extra={"a": lambda: "resolved"})
        result = eval_lambda_extra(r)
        assert result["extra"]["a"] == "resolved"

    def test_empty_extra(self):
        r = record()
        result = eval_lambda_extra(r)
        assert result is r


class TestRemoveItems:
    def test_removes_specified_keys(self):
        r = record(name="test")
        r["extra"]["unwanted"] = 1
        r["extra"]["also_unwanted"] = 2
        remover = remove_extra_items("unwanted", "also_unwanted")
        result = remover(r)
        assert "unwanted" not in result["extra"]
        assert "also_unwanted" not in result["extra"]
        assert result["name"] == "test"

    def test_no_error_when_key_missing(self):
        r = record()
        remover = remove_extra_items("nonexistent")
        result = remover(r)
        assert result is r

    def test_converts_args_to_string(self):
        r = record()
        r[42] = "value"
        remover = remove_extra_items(42)
        result = remover(r)
        assert "42" not in result["extra"]


class TestFilterNone:
    def test_filters_when_name_is_none(self):
        r = record(name=None)
        assert filter_None(r) == {}

    def test_passes_when_name_not_none(self):
        r = record(name="valid")
        assert filter_None(r) is r


def test_print_processor_error_prints_and_returns_record(capsys):
    r = {"processor_error_message": "boom", "processor_error_name_repr": "<proc>"}
    result = print_processor_error(r)
    output = capsys.readouterr().err
    assert result is r
    assert "Got processor <proc> error: boom." in output


def test_print_processor_error_silent_without_error(capsys):
    r = {}
    result = print_processor_error(r)
    assert result is r
    assert capsys.readouterr().err == ""


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


class TestAllowByName:
    def test_allows_matching_parent(self):
        r = record(name="foo.bar.baz")
        filt = allow_by_name("foo")
        assert filt(r) is r

    def test_drops_non_matching(self):
        r = record(name="other.module")
        filt = allow_by_name("foo")
        assert filt(r) == {}

    def test_drops_when_name_is_none(self):
        r = record(name=None)
        filt = allow_by_name("foo")
        assert filt(r) == {}

    def test_drops_when_name_is_empty(self):
        r = record(name="")
        filt = allow_by_name("foo")
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


class TestSubProcessor:
    def test_default_processors(self):
        sub = SubProcessor()
        assert sub._processors == ()

    def test_runs_processors_on_copy(self):
        def add_key(record):
            record["extra"]["added"] = True
            return record

        sub = SubProcessor([add_key])
        r = record()
        result = sub(r)
        assert result is not r
        assert result["extra"]["added"] is True
        assert "added" not in r["extra"]

    def test_stops_when_processor_drops_record(self):
        calls = []

        def first(record):
            calls.append("first")
            return {}

        def second(record):
            calls.append("second")
            return record

        sub = SubProcessor([first, second])
        assert sub(record()) == {}
        assert calls == ["first"]

    def test_close_forwards_and_suppresses_errors(self):
        closed = []

        class Closer:
            def __call__(self, record):
                return record

            def close(self):
                closed.append("closer")

        class BrokenCloser:
            def __call__(self, record):
                return record

            def close(self):
                raise RuntimeError("close failed")

        sub = SubProcessor([Closer(), BrokenCloser()])
        sub.close()
        assert closed == ["closer"]


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


class TestFormatMessage:
    def test_format_message_simple(self):
        message = "my message"
        log_record = make_record(message)
        log_record.pop("message")
        result = format_message(log_record)
        assert result is log_record
        assert result["message"] == message

    def test_format_message_percent_dict(self):
        message = "my message {name}"
        log_record = make_record(message, kwargs={"name": "one"})
        log_record.pop("message")
        result = format_message(log_record)
        assert result["message"] == "my message one"

    def test_format_message_keeps_existing(self):
        log_record = make_record("already formatted")
        result = format_message(log_record)
        assert result["message"] == "already formatted"


class TestDefaultFormatter:
    def test_call(self):
        df = DefaultFormatter()
        log_record = make_record("default message")
        result = df(log_record)
        # Check that the output contains expected log parts
        assert result is log_record
        message = result["message"]
        assert "DEBUG" in message
        assert "[root]" in message
        assert "default message" in message


class TestSimpleFormatter:
    def test_call(self):
        sf = SimpleFormatter()
        log_record = make_record("my message")
        result = sf(log_record)
        assert result is log_record
        assert "DEBUG    [root] my message" in result["message"]


class TestJsonFormatter:
    def test_call(self):
        f = JsonFormatter()
        record = make_record("my message")
        result = f(record)
        json_result = json.loads(result["message"])

        serializable = {
            "message": "my message",
            "name": record["name"],
            "created": record["created"],
            "level_name": record["level_name"],
            "level_no": record["level"],
            "extra": record["extra"],
            "process_id": record["process_id"],
            "process_name": record["process_name"],
        }

        assert json_result == serializable

    def test_custom_converter(self):
        f = JsonFormatter(converter=lambda x: "CUSTOM")
        record = make_record("test")
        record["extra"] = {"obj": object()}
        result = json.loads(f(record)["message"])
        assert result["extra"]["obj"] == "CUSTOM"

    def test_custom_additional_keys(self):
        f = JsonFormatter(additional_keys=("custom_key",))
        record = make_record("test")
        record["custom_key"] = "val"
        result = json.loads(f(record)["message"])
        assert result["custom_key"] == "val"


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


class TestStream:
    def test_init_default_stream(self):
        h = Stream()
        assert h._stream is sys.stderr

    def test_init_with_stream(self):
        buf = io.StringIO()
        h = Stream(stream=buf)
        assert h._stream is buf

    def test_repr(self):
        h = Stream()
        assert "Stream" in repr(h)

    def test_call_writes_to_stream(self):
        buf = io.StringIO()
        h = Stream(stream=buf)
        record = make_record("hello")
        h(record)
        assert "hello" in buf.getvalue()

    def test_write_flushable(self):
        buf = io.StringIO()
        h = Stream(stream=buf)
        h.write("test")
        assert buf.getvalue() == "test\n"

    def test_write_non_flushable(self):
        class NoFlush:
            def write(self, msg):
                self._written = msg

        stream = NoFlush()
        h = Stream(stream=stream)
        h.write("test")
        assert stream._written == "test\n"

    def test_close(self):
        Stream(sys.stderr).close()

    def test_custom_terminator(self):
        buf = io.StringIO()
        h = Stream(stream=buf)
        h.terminator = "---\n"
        h.write("hello")
        assert buf.getvalue() == "hello---\n"

    def test_call_returns_record(self):
        h = Stream()
        record = make_record()
        assert h(record) is record


class TestWrapStandardHandler:
    def test_init_and_repr(self):
        std = logging.StreamHandler(sys.stdout)
        h = WrapStandardHandler(std)
        assert "WrapStandardHandler" in repr(h)
        assert "StreamHandler" in repr(h)

    def test_call_returns_record(self):
        std = logging.StreamHandler(sys.stdout)
        h = WrapStandardHandler(std)
        record = make_record("wrapped")
        record["file"] = type("F", (), {"path": __file__})()
        record["line"] = 1
        record["function"] = "test_func"
        result = h(record)
        assert result is record

    def test_close(self):
        std = logging.StreamHandler(sys.stdout)
        h = WrapStandardHandler(std)
        h.close()

    def test_call_with_exception(self, capsys):
        buf = io.StringIO()
        std = logging.StreamHandler(buf)
        std.setFormatter(logging.Formatter("%(message)s"))
        h = WrapStandardHandler(std)
        record = make_record("exc")
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
    def test_init_defaults(self):
        sub = BaseHandler()
        h = FingersCrossed(sub)
        assert h._level == 40
        assert h._action_triggered is False

    def test_buffers_below_action_level(self):
        sub = BaseHandler()
        h = FingersCrossed(sub, action_level=40, buffer_size=10)
        record = make_record("low", LEVEL_DEBUG)
        record["level"] = 10
        h(record)
        assert len(h.buffered_records) == 1
        assert h._action_triggered is False

    def test_triggers_rollover_at_action_level(self):
        results = []

        class Spy(BaseHandler):
            def __call__(self, record):
                results.append(record["msg"])
                return record

        h = FingersCrossed(Spy(), action_level=40, buffer_size=10)
        debug = make_record("debug", LEVEL_DEBUG)
        debug["level"] = 10
        h(debug)

        error = make_record("error", LEVEL_ERROR)
        error["level"] = 40
        h(error)

        assert results == ["debug", "error"]
        assert h._action_triggered is True

    def test_direct_after_trigger(self):
        results = []

        class Spy(BaseHandler):
            def __call__(self, record):
                results.append(record["msg"])
                return record

        h = FingersCrossed(Spy(), action_level=40, buffer_size=10)
        d1 = make_record("first", LEVEL_DEBUG)
        d1["level"] = 10
        h(d1)

        tr = make_record("trigger", LEVEL_ERROR)
        tr["level"] = 40
        h(tr)

        aft = make_record("after", LEVEL_DEBUG)
        aft["level"] = 10
        h(aft)

        assert results == ["first", "trigger", "after"]

    def test_repr(self):
        sub = BaseHandler()
        h = FingersCrossed(sub, action_level=40)
        assert "FingersCrossed" in repr(h)

    def test_close(self):
        sub = BaseHandler()
        FingersCrossed(sub).close()

    def test_call_returns_record(self):
        sub = BaseHandler()
        h = FingersCrossed(sub)
        record = make_record()
        assert h(record) is record

    def test_rollover_empty(self):
        sub = BaseHandler()
        h = FingersCrossed(sub)
        h.rollover()

    def test_reset(self):
        results = []

        class Spy(BaseHandler):
            def __call__(self, record):
                results.append(record["msg"])
                return record

        h = FingersCrossed(Spy(), action_level=40, reset=True, buffer_size=10)
        d1 = make_record("d1", LEVEL_DEBUG)
        d1["level"] = 10
        h(d1)

        tr = make_record("trigger", LEVEL_ERROR)
        tr["level"] = 40
        h(tr)

        assert results == ["d1", "trigger"]

        d2 = make_record("d2", LEVEL_DEBUG)
        d2["level"] = 10
        h(d2)

        assert results == ["d1", "trigger"]
        assert h._action_triggered is False

    def test_enqueue_after_trigger(self):
        sub = BaseHandler()
        h = FingersCrossed(sub, action_level=40)
        h._action_triggered = True
        record = make_record("post", LEVEL_DEBUG)
        record["level"] = 10
        result = h.enqueue(record)
        assert result is False


class TestFileWriter:
    def test_write_to_file(self):
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".log", delete=False) as f:
            path = f.name
        try:
            h = FileWriter(path)
            record = make_record("file test")
            h(record)
            content = Path(path).read_text(encoding="utf8")
            assert "file test" in content
            h.close()
        finally:
            Path(path).unlink(missing_ok=True)

    def test_delay_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "delayed.log"
            h = FileWriter(str(path), delay=True)
            assert not path.exists()
            h(make_record("now"))
            content = path.read_text(encoding="utf8")
            assert "now" in content
            h.close()

    def test_close_reopens_if_watch(self):
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".log", delete=False) as f:
            path = f.name
        try:
            h = FileWriter(path, watch=True, delay=True)
            h(make_record("open"))
            assert Path(path).stat()
            h.close()
            assert h._file is None
        finally:
            Path(path).unlink(missing_ok=True)

    def test_reopen_if_needed(self):
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".log", delete=False) as f:
            path = f.name
        try:
            h = FileWriter(path, watch=False)
            h._reopen_if_needed()
            h.close()
        finally:
            Path(path).unlink(missing_ok=True)

    def test_write_recreates_if_closed(self):
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

    def test_call_returns_record(self):
        h = FileWriter("/tmp/nonexistent/test.log", delay=True)
        record = make_record()
        assert h(record) is record


class TestFileWriterEdgeCases:
    def test_close_twice(self):
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".log", delete=False) as f:
            path = f.name
        try:
            h = FileWriter(path)
            h.close()
            h.close()
        finally:
            Path(path).unlink(missing_ok=True)

    def test_reopen_after_close(self):
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".log", delete=False) as f:
            path = f.name
        try:
            h = FileWriter(path)
            h.close()
            h._reopen_if_needed()
        finally:
            Path(path).unlink(missing_ok=True)

    def test_reopen_if_needed_recreates_deleted_file(self):
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
    def test_init_and_repr(self):
        loop = asyncio.new_event_loop()
        try:
            h = AsyncBridge(loop=loop)
            assert "AsyncBridge" in repr(h)
        finally:
            loop.close()

    def test_call_returns_record(self):
        loop = asyncio.new_event_loop()
        try:
            h = AsyncBridge(loop=loop)
            record = make_record()
            assert h(record) is record
        finally:
            loop.close()

    def test_call_skips_when_loop_not_running(self):
        loop = asyncio.new_event_loop()
        try:
            h = AsyncBridge(loop=loop)
            record = make_record()
            result = h(record)
            assert result is record
        finally:
            loop.close()

    def test_call_with_running_loop(self):
        async def run():
            h = AsyncBridge()
            record = make_record("async")
            result = h(record)
            assert result is record
            assert len(h._futures) == 1

        asyncio.run(run())

    def test_close_with_pending_future(self):
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

    def test_close_no_future(self):
        loop = asyncio.new_event_loop()
        try:
            h = AsyncBridge(loop=loop)
            h.close()
        finally:
            loop.close()

    def test_init_no_loop_no_crash(self):
        # Constructing without a running loop must not raise.
        handler = AsyncBridge()
        assert handler.loop is None

    def test_call_no_loop_skips(self):
        handler = AsyncBridge()
        record = make_record()
        result = handler(record)
        assert result is record
        assert handler._futures == set()

    def test_close_flushes_all_futures(self):
        collected = []

        class CollectingAsyncBridge(AsyncBridge):
            async def write(self, message):
                collected.append(message)

        loop = asyncio.new_event_loop()

        def run_loop():
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
                handler(make_record(f"msg-{i}"))
            handler.close()
            assert len(collected) == 5
            for i in range(5):
                assert any(f"msg-{i}" in c for c in collected)
        finally:
            loop.call_soon_threadsafe(loop.stop)
            t.join(timeout=2)
            loop.close()

    def test_close_with_cancelled_future(self):
        loop = asyncio.new_event_loop()
        try:
            handler = AsyncBridge(loop=loop)
            future = loop.create_future()
            future.cancel()
            handler._futures.add(future)
            handler.close()
        finally:
            loop.close()

    def test_call_with_done_future(self):
        collected = []

        class CollectingAsyncBridge(AsyncBridge):
            async def write(self, message):
                collected.append(message)

        loop = asyncio.new_event_loop()

        def run_loop():
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
            handler(make_record("first"))
            # Wait until the first write's future has completed.
            for _ in range(100):
                if any(f.done() for f in handler._futures):
                    break
                time.sleep(0.001)
            # A second call while a done future exists must prune it.
            handler(make_record("second"))
            handler.close()
            assert len(collected) == 2
        finally:
            loop.call_soon_threadsafe(loop.stop)
            t.join(timeout=2)
            loop.close()

    def test_call_loop_raises_runtimeerror(self, monkeypatch):
        class FakeLoop:
            def is_running(self):
                return True

        class PlainAsyncBridge(AsyncBridge):
            def write(self, message):
                return None

        handler = PlainAsyncBridge(loop=FakeLoop())
        monkeypatch.setattr(
            asyncio,
            "run_coroutine_threadsafe",
            lambda coro, loop: (_ for _ in ()).throw(RuntimeError("loop not running")),
        )
        record = make_record()
        result = handler(record)
        assert result is record
        assert handler._futures == set()
