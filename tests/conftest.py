from __future__ import annotations

import contextlib
import logging
from typing import Any, Iterator

import pytest

from plainlog import logger
from plainlog._base import Record
from plainlog._logger import logger_core


class DummyHandlerOld:
    def __init__(self) -> None:
        self._records = []

    def __call__(self, record: Record) -> Any:
        self._records.append(record)
        return record

    @property
    def records(self) -> Any:
        logger_core.wait_for_processed()
        return self._records

    def first(self) -> Any:
        logger_core.wait_for_processed()
        return self._records[0]

    def clear(self) -> None:
        self._records.clear()


class DummyHandler:
    def __init__(self) -> None:
        self._records = []

    def __call__(self, record: Record) -> Any:
        self._records.append(record)
        return record

    @property
    def records(self) -> Any:
        logger_core.wait_for_processed()
        return self._records

    def first(self) -> Any:
        logger_core.wait_for_processed()
        return self._records[0]

    def clear(self) -> None:
        self._records.clear()


@pytest.fixture
def thandler() -> Iterator[DummyHandler]:
    dh = DummyHandler()

    logger.configure(level="DEBUG", processors=[dh])

    yield dh

    logger.configure(level="DEBUG", processors=())
    dh.clear()


@contextlib.contextmanager
def make_logging_logger(
    name: str,
    handler: logging.Handler,
    fmt: str = "%(message)s",
    level: str | int = "DEBUG",
) -> Iterator[logging.Logger]:
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
