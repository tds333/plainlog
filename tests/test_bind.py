import pytest

from plainlog import logger, logger_core


def test_bind_after_add(thandler):
    logger_bound = logger.bind(a=0)
    logger_bound.debug("A")

    record = thandler.first()

    assert record["extra"].get("a") == 0
    assert record["msg"] == "A"


def test_bind_before_add(thandler):
    logger_bound = logger.bind(a=0)
    logger_bound.debug("A")

    record = thandler.first()

    assert record["extra"].get("a") == 0
    assert record["msg"] == "A"


def test_add_using_bound(thandler):
    # thandler resets als extra stuff of core
    logger_core.configure(extra={"a": -1})
    logger_bound = logger.bind(a=0)
    logger.debug("A")
    logger_bound.debug("B")

    assert thandler.records

    record = thandler.records[0]

    assert record["extra"].get("a") == -1
    assert record["msg"] == "A"

    record = thandler.records[1]

    assert record["extra"].get("a") == 0
    assert record["msg"] == "B"


def test_unbind(thandler):
    lb = logger.bind(a=0)
    lb.debug("A")
    lb = lb.unbind("a")
    lb.debug("B")

    assert thandler.records
    record = thandler.records[0]
    assert record["extra"].get("a") == 0
    assert record["msg"] == "A"

    record = thandler.records[1]
    assert record["extra"].get("a") is None
    assert record["msg"] == "B"
