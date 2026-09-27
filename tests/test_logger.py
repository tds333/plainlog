from __future__ import annotations

import io
import logging
import pickle
import sys
from contextlib import closing
from typing import Any

import pytest

from plainlog import logger
from plainlog._base import Record
from plainlog._logger import (
    LEVEL_CRITICAL,
    LEVEL_DEBUG,
    LEVEL_ERROR,
    LEVEL_INFO,
    LEVEL_WARNING,
    Core,
    Logger,
    _validate_level,
    _validate_name,
    logger_core,
)
from tests.conftest import DummyHandler


def test_logger_repr() -> None:
    rstring = repr(logger)

    assert rstring == "<plainlog.Logger name='root' core=<plainlog.Core(name='CORE')>>"


def test_logger_new() -> None:
    new_logger = logger.new(name="new")

    assert "new" in repr(new_logger)


def test_validate_name_string() -> None:
    assert _validate_name("test") == "test"


def test_validate_name_raises_on_non_string() -> None:
    with pytest.raises(ValueError, match="Name must be a string"):
        _validate_name(123)  # type: ignore


def test_validate_level_by_int() -> None:
    result = _validate_level(10)
    assert isinstance(result, int)
    assert result == 10


def test_validate_level_by_name() -> None:
    result = _validate_level("INFO")
    assert isinstance(result, int)
    assert result == 20


def test_validate_level_by_level() -> None:
    expected = LEVEL_ERROR
    result = _validate_level(expected)
    assert result == expected


def test_validate_level_raises_on_invalid() -> None:
    with pytest.raises(ValueError, match="Unknown level"):
        _validate_level("INVALID")


def test_logger_debug(thandler: DummyHandler) -> None:
    message = "log in DEBUG"
    logger.debug(message)

    record = thandler.first()

    assert record["msg"] == message
    assert record["level"] == LEVEL_DEBUG


def test_logger_info(thandler: DummyHandler) -> None:
    message = "log in INFO"
    logger.info(message)

    record = thandler.first()

    assert record["msg"] == message
    assert record["level"] == LEVEL_INFO


def test_logger_warning(thandler: DummyHandler) -> None:
    message = "log in WARNING"
    logger.warning(message)

    record = thandler.first()

    assert record["msg"] == message
    assert record["level"] == LEVEL_WARNING


def test_logger_error(thandler: DummyHandler) -> None:
    message = "log in ERROR"
    logger.error(message)

    record = thandler.first()

    assert record["msg"] == message
    assert record["level"] == LEVEL_ERROR


def test_logger_exception(thandler: DummyHandler) -> None:
    message = "log in EXCEPTION"

    logger.exception(message)

    record = thandler.first()

    assert record["msg"] == message
    assert record["level"] == LEVEL_ERROR
    assert record["exception"]


def test_logger_critical(thandler: DummyHandler) -> None:
    message = "log in CRITICAL"
    logger.critical(message)

    record = thandler.first()

    assert record["msg"] == message
    assert record["level"] == LEVEL_CRITICAL


def test_logger_log(thandler: DummyHandler) -> None:
    message = "log in INFO"
    logger.log("INFO", message)

    record = thandler.first()

    assert record["msg"] == message
    assert record["level"] == LEVEL_INFO


def test_logger_level_name_standard(thandler: DummyHandler) -> None:
    logger.info("standard level")

    record = thandler.first()

    assert record["level_name"] == "INFO"


def test_logger_level_name_custom_int(thandler: DummyHandler) -> None:
    logger.log(25, "custom level")

    record = thandler.first()

    assert record["level"] == 25
    assert record["level_name"] == logging.getLevelName(25)


def test_logger_msg_dict(thandler: DummyHandler) -> None:
    message = {"content": "this is a dict"}
    logger.log("INFO", message)

    record = thandler.first()

    assert record["msg"] == message
    assert "message" not in record
    assert record["level"] == LEVEL_INFO


def test_logger_call(thandler: DummyHandler) -> None:
    message = "log in DEBUG"
    assert logger(msg=message) is True

    record = thandler.first()

    assert record["msg"] == message
    assert record["level"] == LEVEL_DEBUG

    assert logger(level="INFO", msg=message) is True

    record = thandler.records[-1]

    assert record["msg"] == message
    assert record["level"] == LEVEL_INFO


def test_logger_name_property() -> None:
    assert logger.name == "root"


def test_logger_pickle_roundtrip(thandler: DummyHandler) -> None:
    lb = logger.bind(x=1, y=2)
    data = pickle.dumps(lb)
    restored = pickle.loads(data)

    assert restored.name == lb.name
    assert restored._data == lb._data
    assert restored._core is logger_core


def test_logger_pickle_can_log(thandler: DummyHandler) -> None:
    lb = logger.bind(user="pickle")
    data = pickle.dumps(lb)
    restored = pickle.loads(data)

    thandler.clear()
    restored.info("from unpickled logger")
    record = thandler.first()
    assert record["msg"] == "from unpickled logger"
    assert record["user"] == "pickle"


def test_logger_pickle_global_core() -> None:
    from plainlog._logger import logger_core

    lb = Logger(logger_core, "pickle_test", a=1)
    data = pickle.dumps(lb)
    restored = pickle.loads(data)
    assert restored._core is logger_core

    assert restored.name == "pickle_test"
    assert restored._data == {"a": 1}


def test_core_processors_property(thandler: DummyHandler) -> None:
    assert logger_core.processors == (thandler,)


def test_logger_context(thandler: DummyHandler) -> None:
    token = Logger.context(user="alice")
    try:
        logger.info("with context")
        record = thandler.first()
        assert record["user"] == "alice"
        assert record["msg"] == "with context"
    finally:
        Logger.reset_context(token)


def test_logger_contextualize(thandler: DummyHandler) -> None:
    with Logger.contextualize(request_id="abc"):
        logger.info("inside context")
        record = thandler.first()
        assert record["request_id"] == "abc"

    thandler.clear()
    logger.info("after context")
    record = thandler.first()
    assert "request_id" not in record


def test_logger_context_isolation(thandler: DummyHandler) -> None:
    token = Logger.context(trace="first")
    Logger.context(trace="second")
    try:
        logger.info("latest wins")
        record = thandler.first()
        assert record["trace"] == "second"
    finally:
        Logger.reset_context(token)


def test_core_log_no_handler_returns_empty() -> None:
    core = Core(name="NO_HANDLER_LOG")
    with closing(core):
        record = core.log({"msg": "direct"})
        assert record is None


class ErrorOnProcess:
    def __call__(self, record: Record) -> Record:
        raise RuntimeError("process failed")


def write_processor_error(record: Record) -> Any:
    sys.stderr.write(str(record.get("processor_error_message")))
    sys.stderr.write(str(record.get("processor_error_name_repr")))
    return record


def test_core_process_error_prints_to_stderr(
    thandler: DummyHandler, capsys: pytest.CaptureFixture[str]
) -> None:
    logger.configure(
        processors=[ErrorOnProcess(), write_processor_error], level="DEBUG"
    )
    logger.info("trigger process error")
    logger_core.wait_for_processed()
    output = capsys.readouterr().err
    assert "ErrorOnProcess" in output
    assert "process failed" in output


class ErrorOnCloseHandler:
    def close(self) -> None:
        raise RuntimeError("close failed")

    def __call__(self, record: Record) -> Any:
        return record


def test_print_error_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    core = Core(name="PRINT_TEST")
    with closing(core):
        core._print_error({"msg": "test"}, "dummy_handler", ValueError("bang"))
        output = capsys.readouterr().err
        assert "Logging error" in output
        assert "dummy_handler" in output
        assert "bang" in output


def test_print_error_suppressed_when_stderr_closed() -> None:
    core = Core(name="PRINT_TEST2")
    with closing(core):
        closed = io.StringIO()
        closed.close()
        old = sys.stderr
        sys.stderr = closed
        try:
            core._print_error({"msg": "test"}, "h", ValueError("bang"))
        finally:
            sys.stderr = old


class FailingStderr:
    closed = False

    def write(self, message: Any) -> None:
        raise OSError("cannot write")


def test_print_error_suppressed_on_oserror() -> None:
    core = Core(name="PRINT_OSERROR")
    with closing(core):
        old = sys.stderr
        sys.stderr = FailingStderr()
        try:
            core._print_error({"msg": "test"}, "h", ValueError("bang"))
        finally:
            sys.stderr = old


def test_logger_no_handler() -> None:
    message = "should not be logged"
    core = Core(name="NO_HANDLER")
    with closing(core):
        core.configure(processors=(), level="DEBUG")
        log = Logger(core, name="test")
        assert log.debug(message) is None
        assert log.info(message) is None
        assert log.warning(message) is None
        assert log.error(message) is None
        assert log.critical(message) is None
        assert log(msg=message) is False


def test_core_close_when_not_alive() -> None:
    core = Core(name="CLOSE_TEST")
    with closing(core):
        core.close()
        core.close()


def test_core_is_alive() -> None:
    core = Core(name="ALIVE_TEST")
    with closing(core):
        assert core.is_alive()
    assert not core.is_alive()


def test_core_print_error_with_exc_info(capsys: pytest.CaptureFixture[str]) -> None:
    core = Core(name="EXC_INFO")
    with closing(core):
        try:
            raise ValueError("from exc_info")
        except ValueError:
            core._print_error({"msg": "test"}, "h")
        output = capsys.readouterr().err
        assert "Logging error" in output
        assert "from exc_info" in output


class BadStrRecord:
    def __str__(self) -> str:
        raise RuntimeError("bad str")


def test_core_print_error_unprintable_record(
    capsys: pytest.CaptureFixture[str],
) -> None:
    core = Core(name="BAD_STR")
    with closing(core):
        core._print_error(BadStrRecord(), "h", ValueError("boom"))  # type: ignore
        output = capsys.readouterr().err
        assert "Unprintable record" in output


def test_logger_new_auto_name() -> None:
    log = logger.new()
    assert log.name.startswith("tests.test_logger")
    assert "test_logger_new_auto_name" in log.name


# co_qualname exists from 3.11 on; PEP 709 inlines comprehensions from 3.12 on.
_HAS_QUALNAME = sys.version_info >= (3, 11)
_HAS_INLINED_COMPREHENSIONS = sys.version_info >= (3, 12)


class _NameTarget:
    """Hosts a method/staticmethod so auto-name detection can be exercised."""

    def method(self) -> str:
        return logger.new().name

    @staticmethod
    def static_method() -> str:
        return logger.new().name


def _nested_outer() -> str:
    def inner() -> str:
        return logger.new().name

    return inner()


def _lambda_site() -> str:
    return (lambda: logger.new().name)()


def _comprehension_site() -> str:
    return [logger.new().name for _ in range(1)][0]


def test_logger_new_auto_name_method() -> None:
    if _HAS_QUALNAME:
        expected = f"{__name__}._NameTarget.method"
    else:
        expected = f"{__name__}.method"

    assert _NameTarget().method() == expected


def test_logger_new_auto_name_staticmethod() -> None:
    if _HAS_QUALNAME:
        expected = f"{__name__}._NameTarget.static_method"
    else:
        expected = f"{__name__}.static_method"

    assert _NameTarget.static_method() == expected


def test_logger_new_auto_name_nested_function() -> None:
    if _HAS_QUALNAME:
        expected = f"{__name__}._nested_outer.inner"
    else:
        expected = f"{__name__}.inner"

    assert _nested_outer() == expected


def test_logger_new_auto_name_lambda() -> None:
    if _HAS_QUALNAME:
        expected = f"{__name__}._lambda_site.<lambda>"
    else:
        expected = f"{__name__}.<lambda>"

    assert _lambda_site() == expected


def test_logger_new_auto_name_comprehension() -> None:
    if _HAS_INLINED_COMPREHENSIONS:
        expected = f"{__name__}._comprehension_site"
    elif _HAS_QUALNAME:
        expected = f"{__name__}._comprehension_site.<listcomp>"
    else:
        expected = f"{__name__}.<listcomp>"

    assert _comprehension_site() == expected


def test_logger_new_auto_name_falls_back_without_module_name() -> None:
    # A frame whose globals have no __name__ yields no detected name, so the
    # parent logger's name is used instead of an empty string.
    namespace: dict = {"logger": logger}
    exec("result = logger.new().name", namespace)

    assert namespace["result"] == logger.name


class BareHandler:
    def __call__(self, record: Record) -> Record:
        return record


def test_core_handler_no_close() -> None:
    core = Core(name="NO_CLOSE")
    with closing(core):
        core.configure(processors=[BareHandler()], level="DEBUG")
        core.configure(processors=[BareHandler()], level="DEBUG")


def test_core_configure_none_keeps_processors() -> None:
    core = Core(name="KEEP_PROCESSORS")
    with closing(core):
        handler = BareHandler()
        core.configure(processors=[handler], level="DEBUG")
        core.configure(processors=None, level="WARNING")
        core.wait_for_processed()
        assert core.processors == (handler,)
        assert core.min_level_no == LEVEL_WARNING


def test_core_reconfigure_suppresses_close_error() -> None:
    core = Core(name="CLOSE_ERROR")
    with closing(core):
        core.configure(processors=[ErrorOnCloseHandler()], level="DEBUG")
        core.configure(processors=(), level="DEBUG")
        assert core.processors == ()


def test_core_worker_log_when_handler_cleared() -> None:
    core = Core(name="LOG_CLEARED")
    with closing(core):
        dh = BareHandler()
        core.configure(processors=[dh], level="DEBUG")
        core.wait_for_processed()
        core.configure(processors=())
        core.wait_for_processed()
        core.log({"msg": "orphaned"})
        core.wait_for_processed()


def test_core_worker_stops_when_record_filtered() -> None:
    calls = []

    def drop(record: Record) -> Any:
        calls.append("drop")
        return {}

    def after(record: Record) -> Any:
        calls.append("after")
        return record

    core = Core(name="FILTER_STOP")
    with closing(core):
        core.configure(processors=[drop, after], level="DEBUG")
        log = Logger(core, name="test")
        log.info("filtered out")
        core.wait_for_processed()
        assert calls == ["drop"]


def test_core_worker_event(capsys: pytest.CaptureFixture[str]) -> None:
    core = Core(name="EVENT_TEST")
    with closing(core):
        core.wait_for_processed()


def test_core() -> None:
    records = []
    message = "other core debug"

    class DummyHandler:
        def __init__(self) -> None:
            self.records = []

        def __call__(self, record: Record) -> Record:
            self.records.append(record)
            return record

    def dummy_processor(record: Record) -> Any:
        nonlocal records
        records.append(record)

        return record

    core_test = Core(name="CORE_TEST")
    dummy_handler = DummyHandler()
    with closing(core_test):
        core_test.configure(processors=[dummy_handler])
        logger_test = Logger(core_test, name="test")
        logger_test.debug(message)

    assert dummy_handler.records
    assert dummy_handler.records[0].get("msg") == message


class HandlerWithoutClose:
    def __call__(self, record: Record) -> Any:
        return record


def test_core_handler_without_close() -> None:
    core = Core(name="NO_CLOSE_ATTR")
    with closing(core):
        core.configure(processors=[HandlerWithoutClose()], level="DEBUG")
        core.configure(processors=[BareHandler()], level="DEBUG")


def test_logger_new_at_module_top_level() -> None:
    from tests._helper_new_at_module_level import LOGGER_NAME

    assert LOGGER_NAME == "tests._helper_new_at_module_level"


class _CapturingHandler:
    def __init__(self) -> None:
        self.records = []

    def __call__(self, record: Record) -> Any:
        self.records.append(record)
        return record


def _verbose_log_site(log: Any) -> Any:
    log.info("verbose message", caller_info=True)
    return _verbose_log_site.__code__.co_firstlineno


def test_verbose_adds_caller_info() -> None:
    handler = _CapturingHandler()
    core = Core(name="VERBOSE")
    with closing(core):
        core.configure(processors=[handler], level="DEBUG")
        log = Logger(core, name="test", caller_info=True)
        base_line = _verbose_log_site(log)
        core.wait_for_processed()
        record = handler.records[0]
        assert record["function"] == "_verbose_log_site"
        assert record["line"] == base_line + 1
        assert record["module"] == "test_logger"
        assert record["file_name"] == "test_logger.py"
        assert record["file_path"].endswith("test_logger.py")
        assert "thread_name" in record


def test_verbose_false_omits_caller_info() -> None:
    handler = _CapturingHandler()
    core = Core(name="NON_VERBOSE")
    with closing(core):
        core.configure(processors=[handler], level="DEBUG")
        log = Logger(core, name="test")
        log.info("plain message")
        core.wait_for_processed()
        record = handler.records[0]
        assert "function" not in record
        assert "line" not in record


def test_call_caller_info_adds_caller_info() -> None:
    handler = _CapturingHandler()
    core = Core(name="CALL_CALLER_INFO")
    with closing(core):
        core.configure(processors=[handler], level="DEBUG")
        log = Logger(core, name="test")
        log.info("with caller info", caller_info=True)
        core.wait_for_processed()
        record = handler.records[0]
        assert record["function"] == "test_call_caller_info_adds_caller_info"
        assert "line" in record


def test_error_defaults_to_caller_info() -> None:
    handler = _CapturingHandler()
    core = Core(name="ERROR_CALLER_INFO")
    with closing(core):
        core.configure(processors=[handler], level="DEBUG")
        log = Logger(core, name="test")
        log.error("boom")
        core.wait_for_processed()
        record = handler.records[0]
        assert record["function"] == "test_error_defaults_to_caller_info"
        assert "line" in record
