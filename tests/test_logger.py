from contextlib import closing
from plainlog import logger, logger_core
from plainlog._logger import (
    Logger,
    Core,
    LEVEL_DEBUG,
    LEVEL_INFO,
    LEVEL_WARNING,
    LEVEL_ERROR,
    LEVEL_CRITICAL,
)


def test_logger_repr():
    rstring = repr(logger)

    assert rstring == "<plainlog.Logger name='root' core=<plainlog.Core(name='CORE')>>"


def test_logger_new():
    new_logger = logger.new(name="new")

    assert "new" in repr(new_logger)


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
    assert record["kwargs"]["exc_info"]


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


def test_logger_call(thandler):
    message = "log in DEBUG"
    record = logger(msg=message)

    assert record["msg"] == message
    assert record["level"] == LEVEL_DEBUG

    record = thandler.first()

    assert record["msg"] == message
    assert record["level"] == LEVEL_DEBUG


def test_core():
    records = []
    message = "other core debug"

    def dummy_processor(record):
        nonlocal records
        records.append(record)

        return record

    core_test = Core(name="CORE_TEST")
    with closing(core_test):
        core_test.configure(processors=dummy_processor)
        logger_test = Logger(
            core_test, name="test", preprocessors=(), processors=(), extra={}
        )
        logger_test.debug(message)

    assert records
    assert records[0].get("msg") == message
