import asyncio
import io
import logging
import sys
import tempfile
from pathlib import Path

import pytest

from plainlog._logger import LEVEL_DEBUG, LEVEL_ERROR
from plainlog._recattrs import Level, RecordException
from plainlog.formatters import DefaultFormatter, SimpleFormatter
from plainlog.handlers import (
    AsyncHandler,
    BaseHandler,
    CollectHandler,
    ConsoleHandler,
    DefaultHandler,
    DevelopHandler,
    FileHandler,
    FingersCrossedHandler,
    JsonHandler,
    ProcessingHandler,
    StreamHandler,
    WrapStandardHandler,
)


def make_record(msg="test", level=None):
    from plainlog._logger import (
        get_now_utc,
        logger_core,
        logger_process,
        plainlog_context,
    )

    level = LEVEL_DEBUG if level is None else level
    return {
        "level": logger_core.level(level),
        "msg": msg,
        "message": str(msg),
        "name": "test",
        "datetime": get_now_utc(),
        "process_id": logger_process.ident,
        "process_name": logger_process.name,
        "context": {**plainlog_context.get({})},
        "extra": {"a": 1},
        "kwargs": {},
    }


class TestBaseHandler:
    def test_preprocess_passthrough(self):
        h = BaseHandler()
        record = make_record()
        assert h.preprocess(record) is record

    def test_process_passthrough(self):
        h = BaseHandler()
        record = make_record()
        assert h.process(record) is record

    def test_close_does_nothing(self):
        BaseHandler().close()


class TestProcessingHandler:
    def test_init_with_defaults(self):
        h = ProcessingHandler()
        assert h._preprocessors == []
        assert h._processors == []
        assert h._handler is None

    def test_preprocess_with_preprocessors(self):
        calls = []

        def p1(r):
            calls.append("p1")
            return r

        def p2(r):
            calls.append("p2")
            return r

        h = ProcessingHandler(preprocessors=[p1, p2])
        record = make_record()
        h.preprocess(record)
        assert calls == ["p1", "p2"]

    def test_preprocess_stops_on_empty(self):
        def p1(r):
            return {}

        def p2(r):
            pytest.fail("should not be called")

        h = ProcessingHandler(preprocessors=[p1, p2])
        assert h.preprocess(make_record()) == {}

    def test_process_with_processors(self):
        calls = []

        def proc(r):
            calls.append("proc")
            return r

        h = ProcessingHandler(processors=[proc])
        h.process(make_record())
        assert calls == ["proc"]

    def test_process_stops_on_empty(self):
        def p1(r):
            return {}

        def p2(r):
            pytest.fail("should not be called")

        h = ProcessingHandler(processors=[p1, p2])
        assert h.process(make_record()) == {}

    def test_process_forwards_to_subhandler(self):
        sub = BaseHandler()
        spy = []

        def wrap(r):
            spy.append(r)
            return r

        sub.process = wrap
        h = ProcessingHandler(processors=[], handler=sub)
        record = make_record()
        h.process(record)
        assert spy == [record]

    def test_close_forwards_to_subhandler(self):
        class CloseSpy(BaseHandler):
            def __init__(self):
                self.closed = False

            def close(self):
                self.closed = True

        sub = CloseSpy()
        h = ProcessingHandler(handler=sub)
        h.close()
        assert sub.closed

    def test_close_skips_when_no_handler(self):
        ProcessingHandler().close()


class TestCollectHandler:
    def test_init_defaults(self):
        h = CollectHandler()
        assert h._handlers == []

    def test_preprocess_chains(self):
        results = []

        class Spy(BaseHandler):
            def preprocess(self, record):
                results.append("pre")
                return record

        h = CollectHandler(handlers=[Spy(), Spy()])
        h.preprocess(make_record())
        assert results == ["pre", "pre"]

    def test_preprocess_stops_on_empty(self):
        class Empty(BaseHandler):
            def preprocess(self, record):
                return {}

        class NeverCalled(BaseHandler):
            def preprocess(self, record):
                pytest.fail("should not be called")

        h = CollectHandler(handlers=[Empty(), NeverCalled()])
        assert h.preprocess(make_record()) == {}

    def test_process_chains(self):
        results = []

        class Spy(BaseHandler):
            def process(self, record):
                results.append("proc")
                return record

        h = CollectHandler(handlers=[Spy(), Spy()])
        h.process(make_record())
        assert results == ["proc", "proc"]

    def test_process_stops_on_empty(self):
        class Empty(BaseHandler):
            def process(self, record):
                return {}

        class NeverCalled(BaseHandler):
            def process(self, record):
                pytest.fail("should not be called")

        h = CollectHandler(handlers=[Empty(), NeverCalled()])
        assert h.process(make_record()) == {}

    def test_close_calls_all(self):
        results = []

        class Spy(BaseHandler):
            def close(self):
                results.append("close")

        h = CollectHandler(handlers=[Spy(), Spy()])
        h.close()
        assert results == ["close", "close"]


class TestStreamHandler:
    def test_init_default_stream(self):
        h = StreamHandler()
        assert h._stream is sys.stderr

    def test_init_with_stream(self):
        buf = io.StringIO()
        h = StreamHandler(stream=buf)
        assert h._stream is buf

    def test_init_with_formatter(self):
        fmt = SimpleFormatter()
        h = StreamHandler(formatter=fmt)
        assert h._formatter is fmt

    def test_repr(self):
        h = StreamHandler()
        assert "StreamHandler" in repr(h)
        assert "SimpleFormatter" in repr(h)

    def test_process_writes_to_stream(self):
        buf = io.StringIO()
        h = StreamHandler(stream=buf)
        record = make_record("hello")
        h.process(record)
        assert "hello" in buf.getvalue()

    def test_write_flushable(self):
        buf = io.StringIO()
        h = StreamHandler(stream=buf)
        h.write("test")
        assert buf.getvalue() == "test\n"

    def test_write_non_flushable(self):
        class NoFlush:
            def write(self, msg):
                self._written = msg

        stream = NoFlush()
        h = StreamHandler(stream=stream)
        h.write("test")
        assert stream._written == "test\n"

    def test_close(self):
        StreamHandler(sys.stderr).close()

    def test_custom_terminator(self):
        buf = io.StringIO()
        h = StreamHandler(stream=buf)
        h.terminator = "---\n"
        h.write("hello")
        assert buf.getvalue() == "hello---\n"

    def test_preprocess_passthrough(self):
        h = StreamHandler()
        record = make_record()
        assert h.preprocess(record) is record


class TestDefaultHandler:
    def test_init(self):
        h = DefaultHandler()
        assert isinstance(h._formatter, DefaultFormatter)

    def test_process(self):
        buf = io.StringIO()
        h = DefaultHandler(stream=buf)
        record = make_record("hi")
        h.process(record)
        assert buf.getvalue()


class TestConsoleHandler:
    def test_init_defaults(self):
        h = ConsoleHandler()
        assert "ConsoleRenderer" in repr(h._formatter)

    def test_process(self):
        buf = io.StringIO()
        h = ConsoleHandler(stream=buf)
        record = make_record("hello")
        h.process(record)
        assert buf.getvalue()

    def test_init_no_color(self):
        buf = io.StringIO()
        h = ConsoleHandler(stream=buf, colors=False)
        h.process(make_record("plain"))
        assert "plain" in buf.getvalue()


class TestDevelopHandler:
    def test_preprocess_adds_caller_info(self):
        h = DevelopHandler()
        record = make_record("dev")
        result = h.preprocess(record)
        assert "file_name" in result
        assert "function" in result
        assert "line" in result

    def test_process(self):
        buf = io.StringIO()
        h = DevelopHandler(stream=buf)
        record = make_record("dev_msg")
        h.process(record)
        assert "dev_msg" in buf.getvalue()


class TestWrapStandardHandler:
    def test_init_and_repr(self):
        std = logging.StreamHandler(sys.stdout)
        h = WrapStandardHandler(std)
        assert "WrapStandardHandler" in repr(h)
        assert "StreamHandler" in repr(h)

    def test_process_returns_record(self):
        std = logging.StreamHandler(sys.stdout)
        h = WrapStandardHandler(std)
        record = make_record("wrapped")
        record["file"] = type("F", (), {"path": __file__})()
        record["line"] = 1
        record["function"] = "test_func"
        result = h.process(record)
        assert result is record

    def test_preprocess_passthrough(self):
        h = WrapStandardHandler(logging.StreamHandler(sys.stdout))
        record = make_record()
        assert h.preprocess(record) is record

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
        h.process(record)
        err_output = capsys.readouterr().err.split("\n")[0]
        assert "Logging error" in err_output or err_output == ""
        assert h is not None


class TestJsonHandler:
    def test_init_defaults(self):
        h = JsonHandler()
        assert "JsonFormatter" in repr(h._formatter)

    def test_process(self):
        buf = io.StringIO()
        h = JsonHandler(stream=buf)
        record = make_record("json_msg")
        h.process(record)
        output = buf.getvalue()
        assert "json_msg" in output
        import json

        parsed = json.loads(output.strip())
        assert parsed["message"] == "json_msg"

    def test_init_with_options(self):
        buf = io.StringIO()
        h = JsonHandler(stream=buf, sort_keys=True, indent=2)
        record = make_record("sorted")
        h.process(record)
        assert '"message": "sorted"' in buf.getvalue()


class TestFingersCrossedHandler:
    def test_init_defaults(self):
        sub = BaseHandler()
        h = FingersCrossedHandler(sub)
        assert h._level == 40
        assert h._action_triggered is False

    def test_buffers_below_action_level(self):
        sub = BaseHandler()
        h = FingersCrossedHandler(sub, action_level=40, buffer_size=10)
        record = make_record("low", LEVEL_DEBUG)
        record["level"] = Level(10, "DEBUG")
        h.process(record)
        assert len(h.buffered_records) == 1
        assert h._action_triggered is False

    def test_triggers_rollover_at_action_level(self):
        results = []

        class Spy(BaseHandler):
            def process(self, record):
                results.append(record["msg"])
                return record

        h = FingersCrossedHandler(Spy(), action_level=40, buffer_size=10)
        debug = make_record("debug", LEVEL_DEBUG)
        debug["level"] = Level(10, "DEBUG")
        h.process(debug)

        error = make_record("error", LEVEL_ERROR)
        error["level"] = Level(40, "ERROR")
        h.process(error)

        assert results == ["debug", "error"]
        assert h._action_triggered is True

    def test_direct_after_trigger(self):
        results = []

        class Spy(BaseHandler):
            def process(self, record):
                results.append(record["msg"])
                return record

        h = FingersCrossedHandler(Spy(), action_level=40, buffer_size=10)
        d1 = make_record("first", LEVEL_DEBUG)
        d1["level"] = Level(10, "DEBUG")
        h.process(d1)

        tr = make_record("trigger", LEVEL_ERROR)
        tr["level"] = Level(40, "ERROR")
        h.process(tr)

        aft = make_record("after", LEVEL_DEBUG)
        aft["level"] = Level(10, "DEBUG")
        h.process(aft)

        assert results == ["first", "trigger", "after"]

    def test_repr(self):
        sub = BaseHandler()
        h = FingersCrossedHandler(sub, action_level=40)
        assert "FingersCrossedHandler" in repr(h)

    def test_close(self):
        sub = BaseHandler()
        FingersCrossedHandler(sub).close()

    def test_preprocess_forwards(self):
        sub = BaseHandler()
        h = FingersCrossedHandler(sub)
        record = make_record()
        assert h.preprocess(record) is record

    def test_rollover_empty(self):
        sub = BaseHandler()
        h = FingersCrossedHandler(sub)
        h.rollover()

    def test_reset(self):
        results = []

        class Spy(BaseHandler):
            def process(self, record):
                results.append(record["msg"])
                return record

        h = FingersCrossedHandler(Spy(), action_level=40, reset=True, buffer_size=10)
        d1 = make_record("d1", LEVEL_DEBUG)
        d1["level"] = Level(10, "DEBUG")
        h.process(d1)

        tr = make_record("trigger", LEVEL_ERROR)
        tr["level"] = Level(40, "ERROR")
        h.process(tr)

        assert results == ["d1", "trigger"]

        d2 = make_record("d2", LEVEL_DEBUG)
        d2["level"] = Level(10, "DEBUG")
        h.process(d2)

        assert results == ["d1", "trigger"]
        assert h._action_triggered is False

    def test_enqueue_after_trigger(self):
        sub = BaseHandler()
        h = FingersCrossedHandler(sub, action_level=40)
        h._action_triggered = True
        record = make_record("post", LEVEL_DEBUG)
        record["level"] = Level(10, "DEBUG")
        result = h.enqueue(record)
        assert result is False


class TestFileHandler:
    def test_write_to_file(self):
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".log", delete=False) as f:
            path = f.name
        try:
            h = FileHandler(path)
            record = make_record("file test")
            h.process(record)
            content = Path(path).read_text(encoding="utf8")
            assert "file test" in content
            h.close()
        finally:
            Path(path).unlink(missing_ok=True)

    def test_delay_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "delayed.log"
            h = FileHandler(str(path), delay=True)
            assert not path.exists()
            h.process(make_record("now"))
            content = path.read_text(encoding="utf8")
            assert "now" in content
            h.close()

    def test_close_reopens_if_watch(self):
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".log", delete=False) as f:
            path = f.name
        try:
            h = FileHandler(path, watch=True, delay=True)
            h.process(make_record("open"))
            assert Path(path).stat()
            h.close()
            assert h._file is None
        finally:
            Path(path).unlink(missing_ok=True)

    def test_reopen_if_needed(self):
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".log", delete=False) as f:
            path = f.name
        try:
            h = FileHandler(path, watch=False)
            h._reopen_if_needed()
            h.close()
        finally:
            Path(path).unlink(missing_ok=True)

    def test_write_recreates_if_closed(self):
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".log", delete=False) as f:
            path = f.name
        try:
            h = FileHandler(path)
            h.close()
            assert h._file is None
            h.write("after close")
            assert h._file is not None
            h.close()
        finally:
            Path(path).unlink(missing_ok=True)

    def test_custom_formatter(self):
        fmt = DefaultFormatter()
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".log", delete=False) as f:
            path = f.name
        try:
            h = FileHandler(path, formatter=fmt)
            assert h._formatter is fmt
            h.close()
        finally:
            Path(path).unlink(missing_ok=True)

    def test_preprocess_passthrough(self):
        h = FileHandler("/tmp/nonexistent/test.log", delay=True)
        record = make_record()
        assert h.preprocess(record) is record


class TestFileHandlerEdgeCases:
    def test_close_twice(self):
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".log", delete=False) as f:
            path = f.name
        try:
            h = FileHandler(path)
            h.close()
            h.close()
        finally:
            Path(path).unlink(missing_ok=True)

    def test_reopen_after_close(self):
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".log", delete=False) as f:
            path = f.name
        try:
            h = FileHandler(path)
            h.close()
            h._reopen_if_needed()
        finally:
            Path(path).unlink(missing_ok=True)


class TestAsyncHandler:
    def test_init_and_repr(self):
        loop = asyncio.new_event_loop()
        try:
            h = AsyncHandler(loop=loop)
            assert "AsyncHandler" in repr(h)
            assert "SimpleFormatter" in repr(h)
        finally:
            loop.close()

    def test_preprocess_passthrough(self):
        loop = asyncio.new_event_loop()
        try:
            h = AsyncHandler(loop=loop)
            record = make_record()
            assert h.preprocess(record) is record
        finally:
            loop.close()

    def test_process_skips_when_loop_not_running(self):
        loop = asyncio.new_event_loop()
        try:
            h = AsyncHandler(loop=loop)
            record = make_record()
            result = h.process(record)
            assert result is record
        finally:
            loop.close()

    def test_process_with_running_loop(self):
        async def run():
            h = AsyncHandler()
            record = make_record("async")
            result = h.process(record)
            assert result is record
            assert h.last_future is not None

        asyncio.run(run())

    def test_close_with_last_future(self):
        from concurrent.futures import Future

        loop = asyncio.new_event_loop()
        try:
            h = AsyncHandler(loop=loop)
            f: Future = Future()
            f.set_result(None)
            h.last_future = f
            h.close()
        finally:
            loop.close()

    def test_close_no_future(self):
        loop = asyncio.new_event_loop()
        try:
            h = AsyncHandler(loop=loop)
            h.close()
        finally:
            loop.close()
