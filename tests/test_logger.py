from contextlib import closing
from plainlog import logger, logger_core
from plainlog._logger import Logger, Core


def test_logger_repr():
    rstring = repr(logger)

    assert rstring == "<plainlog.Logger name='root' core=<plainlog.Core>>"


def test_logger_new():
    new_logger = logger.new(name="new")

    assert "new" in repr(new_logger)


def test_logger_debug(thandler):
    message = "log in DEBUG"
    logger.debug(message)

    record = thandler.first()

    assert record["msg"] == message


def test_core():
    records = []
    message = "other core debug"

    def dummy_processor(record):
        nonlocal records
        records.append(record)

        return record

    core_test = Core()
    with closing(core_test):
        core_test.configure(processors=dummy_processor)
        logger_test = Logger(core_test, name="test", preprocessors=(), processors=(), extra={})
        logger_test.debug(message)

    assert records
    assert records[0].get("msg") == message
