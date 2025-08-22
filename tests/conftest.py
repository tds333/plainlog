import contextlib
import logging

import pytest

import plainlog


# @pytest.fixture(autouse=True)
# def reset_logger():
#     def reset():
#         plainlog.logger_core.remove()
#         plainlog.logger.__init__(
#             plainlog._logger.Core(), "root", None, None, {}
#         )
#         plainlog._logger.context.set({})

#     reset()
#     yield
#     reset()


class DummyHandler:
    def __init__(self):
        self._records = []

    def __call__(self, record):
        self._records.append(record)
        return record

    @property
    def records(self):
        plainlog.logger_core.wait_for_processed()
        return self._records

    def first(self):
        plainlog.logger_core.wait_for_processed()
        return self._records[0]

    def clear(self):
        self._records.clear()


@pytest.fixture
def thandler():
    dh = DummyHandler()

    plainlog.logger_core.configure(processors=[dh])

    yield dh

    plainlog.logger_core.configure(processors=[])
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
