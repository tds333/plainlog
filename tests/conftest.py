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


@pytest.fixture
def writer():
    records = []
    
    def w(record):
        records.append(record)

    w.records = records
    w.first = lambda: records[0]
    w.clear = lambda: records.clear()

    plainlog.logger_core.add(w, name="writer")

    yield w

    plainlog.logger_core.remove("writer")
    del records


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
