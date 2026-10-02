"""Testing helpers for plainlog.

This module is framework-agnostic: it never imports pytest or unittest.
Use `capture_logs()` directly, or wrap it in a fixture for your test runner:

    from plainlog.testing import capture_logs

    with capture_logs() as logs:
        logger.info("hello")
    assert logs.messages == ["hello"]
"""

from __future__ import annotations

import contextlib
from typing import Callable, Iterator, Optional, Union

from ._base import Record
from ._logger import LEVEL_NOTSET, Logger, logger
from .processors import SimpleFormatter, get_formatted_message


class PlainlogCapture:
    """Caplog-like capture object for plainlog records.

    Instances are valid plainlog processors: calling one appends the record to
    an internal list and returns it unchanged.

    Args:
        log: The logger whose Core is captured. Defaults to the module-level
            ``logger``.
    """

    def __init__(self, log: Logger = logger) -> None:
        self._logger = log
        self._records: list[Record] = []
        self._formatter: Optional[Callable[[Record], str]] = None

    def __call__(self, record: Record) -> Record:
        """Append *record* to the capture and return it unchanged."""
        self._records.append(record)
        return record

    def clear(self) -> None:
        """Drop all captured records."""
        self._records.clear()

    @property
    def records(self) -> list[Record]:
        """Captured records as a list copy, after flushing pending records."""
        self._logger.flush()
        return list(self._records)

    def first(self) -> Record:
        """Return the first captured record, after flushing.

        Raises:
            IndexError: If no records were captured.
        """
        self._logger.flush()
        return self._records[0]

    def last(self) -> Record:
        """Return the last captured record, after flushing.

        Raises:
            IndexError: If no records were captured.
        """
        self._logger.flush()
        return self._records[-1]

    @property
    def messages(self) -> list[str]:
        """Captured messages rendered as strings."""
        return [self._format(record) for record in self.records]

    @property
    def text(self) -> str:
        """All captured messages joined by newlines."""
        return "\n".join(self.messages)

    def _format(self, record: Record) -> str:
        if self._formatter is not None:
            return self._formatter(record)
        return get_formatted_message(record)

    def set_level(self, level: Union[str, int]) -> None:
        """Set the Core's minimum level (process-wide).

        Args:
            level: Level name (e.g. ``"INFO"``) or numeric level.
        """
        self._logger._core.configure(processors=None, level=level)

    @contextlib.contextmanager
    def at_level(self, level: Union[str, int]) -> Iterator[None]:
        """Temporarily set the Core's minimum level for a ``with`` block.

        Args:
            level: Level name (e.g. ``"INFO"``) or numeric level.
        """
        previous = self._logger._core.min_level_no
        self._logger._core.configure(processors=None, level=level)
        try:
            yield
        finally:
            self._logger._core.configure(processors=None, level=previous)

    def set_formatter(
        self, formatter: Optional[Union[str, Callable[[Record], str]]]
    ) -> None:
        """Choose how :attr:`text` and :attr:`messages` render records.

        Args:
            formatter: ``None`` restores the default (raw message); a string is
                used as a `SimpleFormatter` format; a callable maps a record to
                a string.
        """
        if formatter is None:
            self._formatter = None
        elif isinstance(formatter, str):
            simple = SimpleFormatter(formatter)

            def _apply(record: Record) -> str:
                return simple(record)["formatted_message"]

            self._formatter = _apply
        else:
            self._formatter = formatter


@contextlib.contextmanager
def capture_logs(log: Logger = logger) -> Iterator[PlainlogCapture]:
    """Capture plainlog records for the duration of the ``with`` block.

    All configured processors are disabled while capturing. The previous level
    is restored on exit; the processor pipeline is left empty, so configure it
    again after the block if you need output.

    Args:
        log: The logger whose Core is captured. Defaults to the module-level
            ``logger``.

    Yields:
        A `PlainlogCapture` holding the recorded records.
    """
    previous_level = log._core.min_level_no
    capture = PlainlogCapture(log)
    log._core.configure(processors=[capture], level=LEVEL_NOTSET)
    try:
        yield capture
    finally:
        log._core.configure(processors=(), level=previous_level)
