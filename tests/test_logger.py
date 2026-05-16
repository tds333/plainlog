import io
import pickle
import sys
from contextlib import closing

import pytest

from plainlog import logger
from plainlog._base import Level, Record
from plainlog._logger import (
    LEVEL_CRITICAL,
    LEVEL_DEBUG,
    LEVEL_ERROR,
    LEVEL_INFO,
    LEVEL_WARNING,
    Command,
    Core,
    Logger,
    _validate_extra,
    _validate_level,
    _validate_name,
)
from plainlog.handlers import BaseHandler


def test_logger_repr():
    rstring = repr(logger)

    assert rstring == "<plainlog.Logger name='root' core=<plainlog.Core(name='CORE')>>"


def test_logger_new():
    new_logger = logger.new(name="new")

    assert "new" in repr(new_logger)


def test_validate_extra_none():
    assert _validate_extra(None) == {}


def test_validate_extra_dict():
    extra = {"a": 1, "b": 2}
    result = _validate_extra(extra)
    assert result == extra
    assert result is not extra


def test_validate_extra_raises_on_non_mapping():
    with pytest.raises(ValueError, match="Extra must be a Mapping"):
        _validate_extra("not a dict")


def test_validate_name_string():
    assert _validate_name("test") == "test"


def test_validate_name_raises_on_non_string():
    with pytest.raises(ValueError, match="Name must be a string"):
        _validate_name(123)


def test_validate_level_by_int():
    result = _validate_level(10)
    assert isinstance(result, Level)
    assert result.no == 10
    assert result.name == "DEBUG"


def test_validate_level_by_name():
    result = _validate_level("INFO")
    assert isinstance(result, Level)
    assert result.no == 20
    assert result.name == "INFO"


def test_validate_level_by_level():
    expected = LEVEL_ERROR
    result = _validate_level(expected)
    assert result == expected


def test_validate_level_raises_on_invalid():
    with pytest.raises(ValueError, match="Invalid log level"):
        _validate_level("INVALID")


def test_logger_debug(thandler):
    message = "log in DEBUG"
    logger.debug(message)

    record = thandler.first()

    assert record["msg"] == message
    assert record["level"] == LEVEL_DEBUG


def test_logger_info(thandler):
    message = "log in INFO"
    logger.info(message)

    record = thandler.first()

    assert record["msg"] == message
    assert record["level"] == LEVEL_INFO


def test_logger_warning(thandler):
    message = "log in WARNING"
    logger.warning(message)

    record = thandler.first()

    assert record["msg"] == message
    assert record["level"] == LEVEL_WARNING


def test_logger_error(thandler):
    message = "log in ERROR"
    logger.error(message)

    record = thandler.first()

    assert record["msg"] == message
    assert record["level"] == LEVEL_ERROR


def test_logger_exception(thandler):
    message = "log in EXCEPTION"

    logger.exception(message)

    record = thandler.first()

    assert record["msg"] == message
    assert record["level"] == LEVEL_ERROR
    assert record["exc_info"]


def test_logger_critical(thandler):
    message = "log in CRITICAL"
    logger.critical(message)

    record = thandler.first()

    assert record["msg"] == message
    assert record["level"] == LEVEL_CRITICAL


def test_logger_log(thandler):
    message = "log in INFO"
    logger.log("INFO", message)

    record = thandler.first()

    assert record["msg"] == message
    assert record["level"] == LEVEL_INFO


def test_logger_msg_dict(thandler):
    message = {"content": "this is a dict"}
    logger.log("INFO", message)

    record = thandler.first()

    assert record["msg"] == message
    assert record["message"] == str(message)
    assert record["level"] == LEVEL_INFO


def test_logger_call(thandler):
    message = "log in DEBUG"
    record = logger(msg=message)

    assert record["msg"] == message
    assert record["level"] == LEVEL_DEBUG

    record = thandler.first()

    assert record["msg"] == message
    assert record["level"] == LEVEL_DEBUG

    record = logger(level="INFO", msg=message)

    assert record["msg"] == message
    assert record["level"] == LEVEL_INFO


def test_logger_name_property():
    assert logger.name == "root"


def test_logger_extra_property():
    assert logger.extra == {}
    assert logger.extra is not logger._extra


def test_logger_pickle_roundtrip(thandler):
    lb = logger.bind(x=1, y=2)
    data = pickle.dumps(lb)
    restored = pickle.loads(data)

    assert restored.name == lb.name
    assert restored.extra == lb.extra
    assert restored.core is logger.core


def test_logger_pickle_can_log(thandler):
    lb = logger.bind(user="pickle")
    data = pickle.dumps(lb)
    restored = pickle.loads(data)

    thandler.clear()
    restored.info("from unpickled logger")
    record = thandler.first()
    assert record["msg"] == "from unpickled logger"
    assert record["extra"]["user"] == "pickle"


def test_logger_pickle_global_core():
    from plainlog._logger import logger_core

    lb = Logger(logger_core, "pickle_test", {"a": 1})
    data = pickle.dumps(lb)
    restored = pickle.loads(data)

    assert restored.core is logger_core
    assert restored.name == "pickle_test"
    assert restored.extra == {"a": 1}


def test_core_handler_property(thandler):
    assert logger.core.handler is thandler


def test_logger_context(thandler):
    token = Logger.context(user="alice")
    try:
        logger.info("with context")
        record = thandler.first()
        assert record["context"]["user"] == "alice"
        assert record["msg"] == "with context"
    finally:
        Logger.reset_context(token)


def test_logger_contextualize(thandler):
    with Logger.contextualize(request_id="abc"):
        logger.info("inside context")
        record = thandler.first()
        assert record["context"]["request_id"] == "abc"

    thandler.clear()
    logger.info("after context")
    record = thandler.first()
    assert "request_id" not in record["context"]


def test_logger_context_isolation(thandler):
    token = Logger.context(trace="first")
    Logger.context(trace="second")
    try:
        logger.info("latest wins")
        record = thandler.first()
        assert record["context"]["trace"] == "second"
    finally:
        Logger.reset_context(token)


def test_core_level_invalid():
    with pytest.raises(ValueError, match="Invalid level"):
        logger.core.level("NONEXISTENT")


def test_core_log_no_handler_returns_empty():
    core = Core(name="NO_HANDLER_LOG")
    with closing(core):
        record = core.log({"msg": "direct"})
        assert record == {}


class ErrorOnPreprocess(BaseHandler):
    def preprocess(self, record):
        raise RuntimeError("preprocess failed")


def test_core_preprocess_error_prints_to_stderr(thandler, capsys):
    logger.core.configure(handler=ErrorOnPreprocess(), level="DEBUG", print_errors=True)
    logger.info("trigger preprocess error")
    logger.core.wait_for_processed()
    output = capsys.readouterr().err
    assert "Error in handler.preprocess()" in output
    assert "preprocess failed" in output


def test_core_preprocess_error_silent_without_print_errors(thandler):
    logger.core.configure(
        handler=ErrorOnPreprocess(), level="DEBUG", print_errors=False
    )
    logger.info("trigger preprocess error")


class ErrorOnProcess(BaseHandler):
    def process(self, record):
        raise RuntimeError("process failed")


def test_core_process_error_prints_to_stderr(thandler, capsys):
    logger.core.configure(handler=ErrorOnProcess(), level="DEBUG", print_errors=True)
    logger.info("trigger process error")
    logger.core.wait_for_processed()
    output = capsys.readouterr().err
    assert "Logging error" in output
    assert "process failed" in output


def test_core_process_error_silent_without_print_errors(thandler):
    logger.core.configure(handler=ErrorOnProcess(), level="DEBUG", print_errors=False)
    logger.info("trigger process error")
    logger.core.wait_for_processed()


class ErrorOnCloseHandler(BaseHandler):
    def close(self):
        raise RuntimeError("close failed")

    def process(self, record):
        return record


def test_core_close_error_prints_to_stderr(thandler, capsys):
    logger.core.configure(
        handler=ErrorOnCloseHandler(), level="DEBUG", print_errors=True
    )
    logger.core.wait_for_processed()
    logger.core.configure(handler=None, level=None)
    output = capsys.readouterr().err
    assert "Error in handler.close()" in output
    assert "close failed" in output
    # Reset back to thandler for fixture teardown
    logger.core.configure(handler=thandler, level="DEBUG", print_errors=False)


def test_print_error_to_stderr(capsys):
    core = Core(name="PRINT_TEST")
    with closing(core):
        core._print_error({"msg": "test"}, "dummy_handler", ValueError("bang"))
        output = capsys.readouterr().err
        assert "Logging error" in output
        assert "dummy_handler" in output
        assert "bang" in output


def test_print_error_suppressed_when_stderr_closed():
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


def test_logger_no_handler():
    message = "should not be logged"
    core = Core(name="NO_HANDLER")
    with closing(core):
        core.configure(handler=None, level="DEBUG")
        log = Logger(core, name="test", extra={})
        assert log.debug(message) is None
        assert log.info(message) is None
        assert log.warning(message) is None
        assert log.error(message) is None
        assert log.critical(message) is None
        assert log(msg=message) == {}


class FilterOnPreprocess(BaseHandler):
    def preprocess(self, record):
        return {}


def test_core_preprocess_filter(thandler):
    logger.core.configure(handler=FilterOnPreprocess(), level="DEBUG")
    result = logger(msg="should be filtered")
    assert result == {}


def test_core_close_when_not_alive():
    core = Core(name="CLOSE_TEST")
    with closing(core):
        core.close()
        core.close()


def test_core_is_alive():
    core = Core(name="ALIVE_TEST")
    with closing(core):
        assert core.is_alive()
    assert not core.is_alive()


def test_core_print_error_with_exc_info(capsys):
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
    def __str__(self):
        raise RuntimeError("bad str")


def test_core_print_error_unprintable_record(capsys):
    core = Core(name="BAD_STR")
    with closing(core):
        core._print_error(BadStrRecord(), "h", ValueError("boom"))
        output = capsys.readouterr().err
        assert "Unprintable record" in output


def test_core_print_error_oserror(capsys):
    core = Core(name="OSERROR")
    with closing(core):
        capsys.readouterr()
        real_write = sys.stderr.write
        sys.stderr.write = lambda *a: (_ for _ in ()).throw(OSError("bang"))
        try:
            core._print_error({"msg": "test"}, "h", ValueError("boom"))
        finally:
            sys.stderr.write = real_write


def test_logger_new_auto_name():
    log = logger.new()
    assert log.name.startswith("tests.test_logger")
    assert "test_logger_new_auto_name" in log.name


class BareHandler(BaseHandler):
    pass


def test_core_handler_no_close():
    core = Core(name="NO_CLOSE")
    with closing(core):
        core.configure(handler=BareHandler(), level="DEBUG")
        core.configure(handler=BaseHandler(), level="DEBUG")


def test_core_worker_log_when_handler_cleared():
    core = Core(name="LOG_CLEARED")
    with closing(core):
        dh = BaseHandler()
        core.configure(handler=dh, level="DEBUG")
        core.wait_for_processed()
        core.configure(handler=None)
        core.wait_for_processed()
        core._put(Command.LOG, {"msg": "orphaned"})
        core.wait_for_processed()


def test_core_worker_event(capsys):
    core = Core(name="EVENT_TEST")
    with closing(core):
        core.wait_for_processed()


def test_core():
    records = []
    message = "other core debug"

    class DummyHandler(BaseHandler):
        def __init__(self) -> None:
            self.records = []
            super().__init__()

        def process(self, record) -> Record:
            self.records.append(record)
            return record

    def dummy_processor(record):
        nonlocal records
        records.append(record)

        return record

    core_test = Core(name="CORE_TEST")
    dummy_handler = DummyHandler()
    with closing(core_test):
        # core_test.configure(processors=dummy_processor)
        core_test.configure(handler=dummy_handler)
        logger_test = Logger(core_test, name="test", extra={})
        logger_test.debug(message)

    assert dummy_handler.records
    assert dummy_handler.records[0].get("msg") == message
