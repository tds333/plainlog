import io
import logging
import sys

import pytest

from plainlog import logger
from plainlog._dev import ConsoleRenderer
from plainlog._logger import LEVEL_DEBUG, LEVEL_WARNING, logger_core
from plainlog.configure import _profiles, add_profile, apply_log_profile
from plainlog.processors import (
    FingersCrossed,
    JsonFormatter,
    SimpleFormatter,
    Stream,
)


def _find(processors, cls):
    return next(p for p in processors if isinstance(p, cls))


@pytest.fixture(autouse=True)
def _restore_logger():
    processors = logger_core.processors
    level = logger_core.min_level_no
    verbose = logger._verbose

    yield

    logger.configure(processors=list(processors), level=level, verbose=verbose)



class TestApplyLogProfile:
    @pytest.mark.parametrize("name", (*_profiles.keys(),))
    def test_apply_log_profile(self, name):
        apply_log_profile(name, level="DEBUG")
        assert logger.error("Testmessage") is None
        assert logger.debug("Testmessage") is None
        assert logger.info("Testmessage") is None
        assert logger.warning("Testmessage") is None
        assert logger.critical("Testmessage") is None
        assert logger.exception("Testmessage") is None


def test_apply_log_profile_default():
    apply_log_profile(level="DEBUG")
    assert logger.error("ok") is None


def test_apply_log_profile_invalid_name():
    with pytest.raises(ValueError, match="not a valid log profile"):
        apply_log_profile(name="nonexistent")


def test_add_profile_new():
    _profiles.pop("_test_custom", None)

    def custom(level=None, **kwargs):
        pass

    result = add_profile("_test_custom", custom)
    assert result is True
    assert "_test_custom" in _profiles
    apply_log_profile(name="_test_custom")
    _profiles.pop("_test_custom", None)


def test_add_profile_duplicate():
    def stub(level=None, **kwargs):
        pass

    result = add_profile("default", stub)
    assert result is False


def test_default_profile_installs_simple_formatter_on_stdout():
    apply_log_profile("default", level="DEBUG")
    processors = logger_core.processors

    assert isinstance(processors[0], SimpleFormatter)
    assert isinstance(processors[1], Stream)
    assert processors[1]._stream is sys.stdout
    assert logger_core.min_level_no == LEVEL_DEBUG


def test_default_profile_honors_stream_kwarg():
    buf = io.StringIO()
    apply_log_profile("default", level="DEBUG", stream=buf)
    logger.info("routed to buf")
    logger_core.wait_for_processed()

    assert "routed to buf" in buf.getvalue()


def test_default_profile_honors_format_kwarg():
    apply_log_profile("default", level="DEBUG", format="{message}")

    assert logger_core.processors[0]._fmt == "{message}"


def test_develop_profile_is_colored_and_verbose():
    apply_log_profile("develop", level="DEBUG")
    renderer = _find(logger_core.processors, ConsoleRenderer)

    assert renderer._styles.level_info != ""
    assert logger._verbose is True


def test_develop_profile_honors_stream_kwarg():
    buf = io.StringIO()
    apply_log_profile("develop", level="DEBUG", stream=buf)
    logger.info("develop to buf")
    logger_core.wait_for_processed()

    assert "develop to buf" in buf.getvalue()


def test_develop_no_color_profile_has_no_ansi_and_is_verbose():
    apply_log_profile("develop_no_color", level="DEBUG")
    renderer = _find(logger_core.processors, ConsoleRenderer)

    assert renderer._styles.level_info == ""
    assert logger._verbose is True


def test_json_and_cloud_set_expected_indent():
    apply_log_profile("cloud", level="DEBUG")
    assert _find(logger_core.processors, JsonFormatter)._indent is None

    apply_log_profile("json", level="DEBUG")
    assert _find(logger_core.processors, JsonFormatter)._indent == 2


def test_file_profile_writes_to_filename(tmp_path):
    path = tmp_path / "app.log"
    apply_log_profile("file", level="DEBUG", filename=str(path))
    logger.info("to the file")
    logger_core.wait_for_processed()

    assert path.exists()
    assert "to the file" in path.read_text()


def test_fingerscrossed_profile_kwargs_and_stream():
    buf = io.StringIO()
    logger.configure(verbose=False)
    apply_log_profile(
        "fingerscrossed",
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
    assert logger._verbose is False


def test_empty_profile_clears_processors():
    apply_log_profile("default", level="DEBUG")
    assert logger_core.processors

    apply_log_profile("empty")

    assert logger_core.processors == ()


def test_no_init_profile_leaves_processors_untouched():
    marker = lambda record: record  # noqa: E731
    logger.configure(processors=[marker], level="DEBUG")
    before = logger_core.processors

    apply_log_profile("no_init")

    assert logger_core.processors is before


def test_std_handler_default_installs_root_handler_and_forwards_kwargs():
    root = logging.getLogger()
    before = list(root.handlers)
    buf = io.StringIO()

    try:
        apply_log_profile("std_handler_default", level="DEBUG", stream=buf)

        assert [h for h in root.handlers if h not in before], (
            "expected a stdlib root handler to be installed"
        )
        stream = _find(logger_core.processors, Stream)
        assert stream._stream is buf
    finally:
        for handler in root.handlers:
            if handler not in before:
                root.removeHandler(handler)


def test_add_profile_function_receives_level_and_kwargs():
    recorded = {}

    def custom(level=None, **kwargs):
        recorded["level"] = level
        recorded["kwargs"] = kwargs

    _profiles.pop("_test_record", None)
    try:
        assert add_profile("_test_record", custom) is True
        apply_log_profile("_test_record", level="INFO", foo="bar")

        assert recorded == {"level": "INFO", "kwargs": {"foo": "bar"}}
    finally:
        _profiles.pop("_test_record", None)


def test_profile_sets_verbose_explicitly():
    apply_log_profile("develop", level="DEBUG")
    assert logger._verbose is True

    apply_log_profile("default", level="DEBUG")
    assert logger._verbose is False


def test_configure_verbose_none_keeps_current():
    logger.configure(verbose=True)
    logger.configure(processors=[])

    assert logger._verbose is True
