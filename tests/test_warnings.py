import warnings
from unittest.mock import patch

from plainlog import logger
from plainlog.warnings import _showwarning, capture_warnings
from tests.conftest import DummyHandler


def test_capture_warnings_true_replaces_showwarning():
    original = warnings.showwarning
    capture_warnings(True)
    assert warnings.showwarning is _showwarning
    capture_warnings(False)
    assert warnings.showwarning is original


def test_capture_warnings_false_restores_original():
    original = warnings.showwarning
    capture_warnings(True)
    capture_warnings(False)
    assert warnings.showwarning is original


def test_capture_warnings_idempotent_true():
    original = warnings.showwarning
    capture_warnings(True)
    first = warnings.showwarning
    capture_warnings(True)
    assert warnings.showwarning is first
    capture_warnings(False)
    assert warnings.showwarning is original


def test_capture_warnings_idempotent_false():
    original = warnings.showwarning
    capture_warnings(True)
    capture_warnings(False)
    capture_warnings(False)
    assert warnings.showwarning is original


def test_warning_logged_via_py_warnings(thandler):
    capture_warnings(True)
    try:
        warnings.warn("test warning message")
        logger._core.wait_for_processed()
        assert thandler.records
        record = thandler.records[0]
        assert "test warning message" in record["msg"]
        assert record["name"] == "py.warnings"
    finally:
        capture_warnings(False)


def test_warning_with_file_param_delegates_to_original():
    original_showwarning = warnings.showwarning
    capture_warnings(True)
    fake_file = object()
    called = False

    def tracking_showwarning(message, category, filename, lineno, file=None, line=None):
        nonlocal called
        called = True
        assert file is fake_file

    with patch("plainlog.warnings._warnings_showwarning", tracking_showwarning):
        _showwarning("file warning", UserWarning, "test.py", 1, file=fake_file)
        assert called, "original showwarning should have been called when file is set"

    capture_warnings(False)
    assert warnings.showwarning is original_showwarning


def test_warning_formatted_correctly(thandler):
    capture_warnings(True)
    try:
        warnings.warn("formatted message", UserWarning)
        logger._core.wait_for_processed()
        record = thandler.records[0]
        msg = record["msg"]
        assert "formatted message" in msg
        assert "UserWarning" in msg
    finally:
        capture_warnings(False)


def test_multiple_warnings_all_captured(thandler):
    capture_warnings(True)
    try:
        for i in range(5):
            warnings.warn(f"warning {i}")
        logger._core.wait_for_processed()
        assert len(thandler.records) == 5
        msgs = [r["msg"] for r in thandler.records]
        for i in range(5):
            assert any(f"warning {i}" in m for m in msgs)
    finally:
        capture_warnings(False)


def test_capture_warnings_toggle_cycle(thandler):
    original = warnings.showwarning
    for _ in range(3):
        capture_warnings(True)
        assert warnings.showwarning is _showwarning
        capture_warnings(False)
        assert warnings.showwarning is original


def test_warnings_only_logged_when_captured(thandler):
    with warnings.catch_warnings(record=True):
        warnings.warn("pre capture")
    logger._core.wait_for_processed()
    pre_count = len(thandler.records)

    capture_warnings(True)
    try:
        warnings.warn("during capture")
        logger._core.wait_for_processed()
        assert len(thandler.records) == pre_count + 1
    finally:
        capture_warnings(False)
