import contextlib
import logging

import pytest

import plainlog
from plainlog import logger
from plainlog._logger import logger_core
from plainlog.handlers import BaseHandler


class DummyHandlerOld:
    def __init__(self):
        self._records = []

    def __call__(self, record):
        self._records.append(record)
        return record

    @property
    def records(self):
        logger_core.wait_for_processed()
        return self._records

    def first(self):
        logger_core.wait_for_processed()
        return self._records[0]

    def clear(self):
        self._records.clear()


class DummyHandler(BaseHandler):
    def __init__(self):
        self._records = []

    def process(self, record):
        self._records.append(record)
        return record

    @property
    def records(self):
        logger_core.wait_for_processed()
        return self._records

    def first(self):
        logger_core.wait_for_processed()
        return self._records[0]

    def clear(self):
        self._records.clear()


@pytest.fixture
def thandler():
    dh = DummyHandler()

    logger.configure(level="DEBUG", handler=dh)

    yield dh

    logger.configure(level="DEBUG", handler=None)
    dh.clear()


@contextlib.contextmanager
def make_logging_logger(name, handler, fmt="%(message)s", level="DEBUG"):
    logging_logger = logging.getLogger(name)
    logging_logger.setLevel(level)
    formatter = logging.Formatter(fmt)

    handler.setLevel(level)
    handler.setFormatter(formatter)
    logging_logger.addHandler(handler)

    try:
        yield logging_logger
    finally:
        logging_logger.removeHandler(handler)
