from __future__ import annotations

import warnings
from typing import Any
from unittest.mock import patch

from plainlog import logger
from plainlog.warnings import _showwarning, capture_warnings
from tests.conftest import DummyHandler


def test_capture_warnings_true_replaces_showwarning() -> None:
    original = warnings.showwarning
    capture_warnings(True)
    assert warnings.showwarning is _showwarning
    capture_warnings(False)
    assert warnings.showwarning is original


def test_capture_warnings_false_restores_original() -> None:
    original = warnings.showwarning
    capture_warnings(True)
    capture_warnings(False)
    assert warnings.showwarning is original


def test_capture_warnings_idempotent_true() -> None:
    original = warnings.showwarning
    capture_warnings(True)
    first = warnings.showwarning
    capture_warnings(True)
    assert warnings.showwarning is first
    capture_warnings(False)
    assert warnings.showwarning is original


def test_capture_warnings_idempotent_false() -> None:
    original = warnings.showwarning
    capture_warnings(True)
    capture_warnings(False)
    capture_warnings(False)
    assert warnings.showwarning is original


def test_warning_logged_via_py_warnings(thandler: DummyHandler) -> None:
    capture_warnings(True)
    try:
        warnings.warn("test warning message", stacklevel=2)
        logger._core.wait_for_processed()
        assert thandler.records
        record = thandler.records[0]
        assert "test warning message" in record["msg"]
        assert record["name"] == "py.warnings"
    finally:
        capture_warnings(False)


def test_warning_with_file_param_delegates_to_original() -> None:
    original_showwarning = warnings.showwarning
    capture_warnings(True)
    fake_file = object()
    called = False

    def tracking_showwarning(
        message: Any,
        category: type[Warning],
        filename: str,
        lineno: int,
        file: Any = None,
        line: str | None = None,
    ) -> None:
        nonlocal called
        called = True
        assert file is fake_file

    with patch("plainlog.warnings._warnings_showwarning", tracking_showwarning):
        _showwarning("file warning", UserWarning, "test.py", 1, file=fake_file)  # type: ignore
        assert called, "original showwarning should have been called when file is set"

    capture_warnings(False)
    assert warnings.showwarning is original_showwarning


def test_warning_formatted_correctly(thandler: DummyHandler) -> None:
    capture_warnings(True)
    try:
        warnings.warn("formatted message", UserWarning, stacklevel=2)
        logger._core.wait_for_processed()
        record = thandler.records[0]
        msg = record["msg"]
        assert "formatted message" in msg
        assert "UserWarning" in msg
    finally:
        capture_warnings(False)


def test_multiple_warnings_all_captured(thandler: DummyHandler) -> None:
    capture_warnings(True)
    try:
        for i in range(5):
            warnings.warn(f"warning {i}", stacklevel=2)
        logger._core.wait_for_processed()
        assert len(thandler.records) == 5
        msgs = [r["msg"] for r in thandler.records]
        for i in range(5):
            assert any(f"warning {i}" in m for m in msgs)
    finally:
        capture_warnings(False)


def test_capture_warnings_toggle_cycle(thandler: DummyHandler) -> None:
    original = warnings.showwarning
    for _ in range(3):
        capture_warnings(True)
        assert warnings.showwarning is _showwarning
        capture_warnings(False)
        assert warnings.showwarning is original


def test_warnings_only_logged_when_captured(thandler: DummyHandler) -> None:
    with warnings.catch_warnings(record=True):
        warnings.warn("pre capture", stacklevel=2)
    logger._core.wait_for_processed()
    pre_count = len(thandler.records)

    capture_warnings(True)
    try:
        warnings.warn("during capture", stacklevel=2)
        logger._core.wait_for_processed()
        assert len(thandler.records) == pre_count + 1
    finally:
        capture_warnings(False)


def test_showwarning_with_file_before_capture() -> None:
    from plainlog.warnings import _showwarning, _warnings_showwarning, capture_warnings

    capture_warnings(False)
    assert _warnings_showwarning is None
    _showwarning("test msg", UserWarning, "f.py", 1, file=object())  # type: ignore
