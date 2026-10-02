from __future__ import annotations

import io
import logging
import pathlib
import sys
from typing import Any, Iterator

import pytest

from plainlog import logger
from plainlog._dev import ConsoleRenderer
from plainlog._logger import LEVEL_DEBUG, LEVEL_WARNING, logger_core
from plainlog.configure import _profiles, add_profile, configure_log
from plainlog.processors import (
    FingersCrossed,
    JsonFormatter,
    SimpleFormatter,
    Stream,
)


def _find(processors: Any, cls: type) -> Any:
    return next(p for p in processors if isinstance(p, cls))


@pytest.fixture(autouse=True)
def _restore_logger() -> Iterator[Any]:
    processors = logger_core.processors
    level = logger_core.min_level_no

    yield

    configure_log(processors=list(processors), level=level)


class TestConfigureLog:
    @pytest.mark.parametrize("name", (*_profiles.keys(),))
    def test_configure_log_profile(self, name: str) -> None:
        configure_log(profile=name, level="DEBUG")
        assert logger.error("Testmessage") is None
        assert logger.debug("Testmessage") is None
        assert logger.info("Testmessage") is None
        assert logger.warning("Testmessage") is None
        assert logger.critical("Testmessage") is None
        assert logger.exception("Testmessage") is None


def test_configure_log_default_profile() -> None:
    configure_log(profile="default", level="DEBUG")
    assert logger.error("ok") is None


def test_configure_log_without_profile_or_processors_leaves_unchanged() -> None:
    before = logger_core.processors

    configure_log(level="DEBUG")

    assert logger_core.processors is before


def test_configure_log_processors_only() -> None:
    marker = lambda record: record  # noqa: E731

    configure_log(processors=[marker], level="DEBUG")

    assert logger_core.processors == (marker,)


def test_configure_log_combines_processors_and_profile() -> None:
    marker = lambda record: record  # noqa: E731

    configure_log(profile="default", processors=[marker], level="DEBUG")

    processors = logger_core.processors
    assert processors[-1] is marker
    assert isinstance(processors[0], SimpleFormatter)


def test_configure_log_invalid_name() -> None:
    with pytest.raises(ValueError, match="not a valid log profile"):
        configure_log(profile="nonexistent")


def test_add_profile_new() -> None:
    _profiles.pop("_test_custom", None)

    def custom(**kwargs: Any) -> None:
        pass

    result = add_profile("_test_custom", custom)
    assert result is True
    assert "_test_custom" in _profiles
    configure_log(profile="_test_custom")
    _profiles.pop("_test_custom", None)


def test_add_profile_duplicate() -> None:
    def stub(**kwargs: Any) -> None:
        pass

    result = add_profile("default", stub)
    assert result is False


def test_default_profile_installs_simple_formatter_on_stdout() -> None:
    configure_log(profile="default", level="DEBUG")
    processors = logger_core.processors

    assert isinstance(processors[0], SimpleFormatter)
    assert isinstance(processors[1], Stream)
    assert processors[1]._stream is sys.stdout
    assert logger_core.min_level_no == LEVEL_DEBUG


def test_default_profile_honors_stream_kwarg() -> None:
    buf = io.StringIO()
    configure_log(profile="default", level="DEBUG", stream=buf)
    logger.info("routed to buf")
    logger_core.wait_for_processed()

    assert "routed to buf" in buf.getvalue()


def test_default_profile_honors_format_kwarg() -> None:
    configure_log(profile="default", level="DEBUG", format="{message}")

    assert getattr(logger_core.processors[0], "_fmt") == "{message}"  # noqa: B009


def test_develop_profile_is_colored() -> None:
    configure_log(profile="develop", level="DEBUG")
    renderer = _find(logger_core.processors, ConsoleRenderer)

    assert renderer._styles.level_info != ""


def test_develop_profile_honors_stream_kwarg() -> None:
    buf = io.StringIO()
    configure_log(profile="develop", level="DEBUG", stream=buf)
    logger.info("develop to buf")
    logger_core.wait_for_processed()

    assert "develop to buf" in buf.getvalue()


def test_develop_no_color_profile_has_no_ansi() -> None:
    configure_log(profile="develop_no_color", level="DEBUG")
    renderer = _find(logger_core.processors, ConsoleRenderer)

    assert renderer._styles.level_info == ""


def test_json_and_cloud_set_expected_indent() -> None:
    configure_log(profile="cloud", level="DEBUG")
    assert _find(logger_core.processors, JsonFormatter)._indent is None

    configure_log(profile="json", level="DEBUG")
    assert _find(logger_core.processors, JsonFormatter)._indent == 2


def test_file_profile_writes_to_filename(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "app.log"
    configure_log(profile="file", level="DEBUG", filename=str(path))
    logger.info("to the file")
    logger_core.wait_for_processed()

    assert path.exists()
    assert "to the file" in path.read_text()


def test_fingerscrossed_profile_kwargs_and_stream() -> None:
    buf = io.StringIO()
    configure_log(
        profile="fingerscrossed",
        level="DEBUG",
        action_level="WARNING",
        buffer_size=5,
        reset=True,
        stream=buf,
    )
    handler = _find(logger_core.processors, FingersCrossed)

    assert handler._level == LEVEL_WARNING
    assert handler.buffered_records.maxlen == 5
    assert handler._reset is True
    assert handler._processor._stream is buf


def test_empty_profile_clears_processors() -> None:
    configure_log(profile="default", level="DEBUG")
    assert logger_core.processors

    configure_log(profile="empty")

    assert logger_core.processors == ()


def test_no_init_profile_leaves_processors_untouched() -> None:
    marker = lambda record: record  # noqa: E731
    configure_log(processors=[marker], level="DEBUG")
    before = logger_core.processors

    configure_log(profile="no_init")

    assert logger_core.processors is before


def test_no_init_does_not_close_even_with_close_before_configure() -> None:
    closed: list[str] = []

    class Spy:
        def __call__(self, record: Any) -> Any:
            return record

        def close(self) -> None:
            closed.append("closed")

    marker = Spy()
    configure_log(processors=[marker], level="DEBUG")

    configure_log(profile="no_init", close_before_configure=True)

    assert closed == []
    assert logger_core.processors == (marker,)


def test_std_handler_default_installs_root_handler_and_forwards_kwargs() -> None:
    root = logging.getLogger()
    before = list(root.handlers)
    buf = io.StringIO()

    try:
        configure_log(profile="std_handler_default", level="DEBUG", stream=buf)

        assert [h for h in root.handlers if h not in before], (
            "expected a stdlib root handler to be installed"
        )
        stream = _find(logger_core.processors, Stream)
        assert stream._stream is buf
    finally:
        for handler in root.handlers:
            if handler not in before:
                root.removeHandler(handler)


def test_add_profile_function_receives_kwargs() -> None:
    recorded = {}

    def custom(**kwargs: Any) -> None:
        recorded["kwargs"] = kwargs

    _profiles.pop("_test_record", None)
    try:
        assert add_profile("_test_record", custom) is True
        configure_log(profile="_test_record", level="INFO", foo="bar")

        assert recorded == {"kwargs": {"foo": "bar"}}
    finally:
        _profiles.pop("_test_record", None)


def test_configure_log_close_before_configure_closes_previous() -> None:
    closed = []

    class Spy:
        def __call__(self, record: Any) -> Any:
            return record

        def close(self) -> None:
            closed.append("closed")

    def profile(**kwargs: Any) -> Any:
        return [Spy()]

    _profiles.pop("_test_spy", None)
    try:
        assert add_profile("_test_spy", profile) is True
        configure_log(profile="_test_spy", level="DEBUG")
        configure_log(profile="empty", close_before_configure=True)

        assert closed
    finally:
        _profiles.pop("_test_spy", None)
