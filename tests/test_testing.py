from __future__ import annotations

import pytest

from plainlog import logger
from plainlog._base import Record
from plainlog._logger import LEVEL_NOTSET
from plainlog.testing import PlainlogCapture, capture_logs


def test_capture_is_a_processor() -> None:
    capture = PlainlogCapture()
    record: Record = {"msg": "x"}

    assert capture(record) is record
    assert capture.records == [record]


def test_capture_context_isolates_and_restores() -> None:
    previous_level = logger._core.min_level_no

    with capture_logs() as capture:
        logger.info("inside")
        assert [record["msg"] for record in capture.records] == ["inside"]
        assert logger._core.processors == (capture,)
        assert logger._core.min_level_no == LEVEL_NOTSET

    assert logger._core.processors == ()
    assert logger._core.min_level_no == previous_level


def test_records_flush_pending() -> None:
    with capture_logs() as capture:
        logger.info("pending")
        assert [record["msg"] for record in capture.records] == ["pending"]


def test_records_available_after_context_exit() -> None:
    with capture_logs() as capture:
        logger.info("kept")

    assert [record["msg"] for record in capture.records] == ["kept"]


def test_first_and_last() -> None:
    with capture_logs() as capture:
        logger.info("a")
        logger.warning("b")
        assert capture.first()["msg"] == "a"
        assert capture.last()["msg"] == "b"


def test_first_and_last_raise_when_empty() -> None:
    with capture_logs() as capture:
        with pytest.raises(IndexError):
            capture.first()
        with pytest.raises(IndexError):
            capture.last()


def test_clear() -> None:
    with capture_logs() as capture:
        logger.info("x")
        assert capture.records
        capture.clear()
        assert capture.records == []


def test_text_and_messages_default_to_raw_msg() -> None:
    with capture_logs() as capture:
        logger.info("one")
        logger.warning("two")
        assert capture.messages == ["one", "two"]
        assert capture.text == "one\ntwo"


def test_text_is_empty_without_records() -> None:
    with capture_logs() as capture:
        assert capture.text == ""


def test_text_with_non_string_msg() -> None:
    capture = PlainlogCapture()
    record: Record = {"msg": {"a": 1}}

    capture(record)

    assert capture.records == [record]
    assert capture.text == "{'a': 1}"


def test_captures_child_logger_fields() -> None:
    with capture_logs() as capture:
        log = logger.new("child").bind(request_id="abc")
        log.info("hi")
        record = capture.first()
        assert record["name"] == "child"
        assert record["request_id"] == "abc"


def test_set_level_filters_records() -> None:
    with capture_logs() as capture:
        capture.set_level("WARNING")
        logger.info("hidden")
        logger.warning("shown")
        assert [record["msg"] for record in capture.records] == ["shown"]


def test_set_level_rejects_unknown_level() -> None:
    with capture_logs() as capture:
        with pytest.raises(ValueError):
            capture.set_level("NOPE")


def test_at_level_restores_previous_level() -> None:
    with capture_logs() as capture:
        capture.set_level("WARNING")
        with capture.at_level("DEBUG"):
            logger.debug("visible")
        logger.debug("hidden")
        assert [record["msg"] for record in capture.records] == ["visible"]


def test_at_level_restores_on_exception() -> None:
    with capture_logs() as capture:
        capture.set_level("WARNING")
        with pytest.raises(RuntimeError):
            with capture.at_level("DEBUG"):
                raise RuntimeError("boom")
        logger.debug("hidden")
        assert capture.records == []


def test_set_formatter_with_string() -> None:
    with capture_logs() as capture:
        capture.set_formatter("{level_name}: {message}")
        logger.info("hi")
        assert capture.text == "INFO: hi"


def test_set_formatter_with_callable() -> None:
    with capture_logs() as capture:
        capture.set_formatter(lambda record: str(record["msg"]).upper())
        logger.info("hi")
        assert capture.messages == ["HI"]


def test_set_formatter_none_resets() -> None:
    with capture_logs() as capture:
        capture.set_formatter("{message}")
        capture.set_formatter(None)
        logger.info("hi")
        assert capture.text == "hi"


def test_plainlog_fixture_captures(plainlog: PlainlogCapture) -> None:
    logger.info("hello")
    assert [record["msg"] for record in plainlog.records] == ["hello"]


def test_plainlog_fixture_captures_all_levels(plainlog: PlainlogCapture) -> None:
    logger.debug("debug")
    assert logger._core.min_level_no == LEVEL_NOTSET
    assert [record["msg"] for record in plainlog.records] == ["debug"]


def test_records_before_fixture_setup_are_not_captured(
    request: pytest.FixtureRequest,
) -> None:
    logger.info("before")
    plainlog = request.getfixturevalue("plainlog")
    logger.info("after")
    assert [record["msg"] for record in plainlog.records] == ["after"]
