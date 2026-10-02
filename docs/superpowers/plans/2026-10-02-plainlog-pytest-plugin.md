# plainlog pytest plugin Implementation Plan

> **Revision 2026-10-02 — superseded by an importable module.**
> Implemented instead as an importable `plainlog.testing` module
> (`capture_logs()` + `PlainlogCapture`): no `pytest11` entry point, no
> package-shipped `plainlog` fixture, no pytest import. The `plainlog` fixture is
> now a documented user-side `conftest.py` recipe. `make test-cov` was reverted to the
> original pytest-cov command (100% confirmed). See `docs/testing.md`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship an auto-registered pytest plugin exposing a caplog-like `plog` fixture, plus a public `logger.flush()`.

**Architecture:** A new `plainlog.pytest_plugin` module holds a `PlainlogCapture` processor object and a `_capture()` context manager that swaps the Core's pipeline for isolated capture at `NOTSET`, then clears it on exit. A function-scoped `plog` fixture wraps `_capture()`. The module is registered through a `pytest11` entry point; only it imports pytest, so plainlog stays zero-dependency.

**Tech Stack:** Python 3.10+, pytest, plainlog's `Logger`/`Core`, `SimpleFormatter`, `get_formatted_message`.

**Spec:** `docs/superpowers/specs/2026-10-02-plainlog-pytest-plugin-design.md`

## Global Constraints

- Python floor is 3.10; every module starts with `from __future__ import annotations`.
- plainlog core must not import pytest; only `src/plainlog/pytest_plugin.py` may.
- Line length 88; Ruff `E,W,F,I,C,B,ANN` (E731/E501/B008/C901/ANN401 ignored); Google-style docstrings, type hints required.
- Coverage must stay 100% (`make test-cov`).
- Tests are functions, not classes, except when testing a class's methods.
- **Do not commit unless the user explicitly approves.** The commit steps below record the intended staging/message; run them only after permission.
- After adding the entry point, re-sync before running tests: `uv sync` (or `uv run --reinstall-package plainlog pytest` if the `plog` fixture is reported missing).
- After code changes, run `graphify update .`.

## Review Focus

Likely-to-bite inputs/conditions, each pinned by a test below:

1. Non-string `msg` (dict/int/object): `.text`/`.messages` must `str()` it, never raise. (Task 2)
2. Empty capture: `.text` must be `""`, not an error. (Task 2)
3. Invalid level string: `set_level("NOPE")` must raise `ValueError`, not silently pass. (Task 3)
4. Records logged before the fixture is requested: must not appear (no processors installed). (Task 5)
5. Child/bound loggers: extra fields and `name` must survive into captured records. (Task 2)

---

### Task 1: Public `Logger.flush()`

**Files:**
- Modify: `src/plainlog/_logger.py` (add method to `Logger`, near `configure`)
- Test: `tests/test_logger.py`

**Interfaces:**
- Consumes: `Core.wait_for_processed(timeout)` (existing).
- Produces: `Logger.flush(timeout: float | None = None) -> None`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_logger.py`:

```python
def test_logger_flush() -> None:
    captured: list[Record] = []

    def capture(record: Record) -> Record:
        captured.append(record)
        return record

    logger.configure(processors=[capture])
    try:
        logger.info("flush me")
        logger.flush()
        assert len(captured) == 1
    finally:
        logger.configure(processors=())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_logger.py::test_logger_flush -x -v`
Expected: FAIL with `AttributeError: 'Logger' object has no attribute 'flush'`

- [ ] **Step 3: Write minimal implementation**

In `src/plainlog/_logger.py`, add to `Logger` directly after `configure()`:

```python
    def flush(self, timeout: float | None = None) -> None:
        """Block until every queued record has been processed.

        Records are handled on the background Core thread. Call this before
        reading side effects such as captured records or written files.

        Args:
            timeout: Maximum seconds to wait. ``None`` uses the default.
        """
        self._core.wait_for_processed(timeout)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_logger.py::test_logger_flush -x -v`
Expected: PASS

- [ ] **Step 5: Commit (requires user approval)**

```bash
git add src/plainlog/_logger.py tests/test_logger.py
git commit -m "add logger.flush"
```

---

### Task 2: `PlainlogCapture` and `_capture()` context manager

**Files:**
- Create: `src/plainlog/pytest_plugin.py`
- Test: `tests/test_pytest_plugin.py`

**Interfaces:**
- Consumes: `Logger.flush()` (Task 1).
- Produces:
  - `class PlainlogCapture` with `__call__(record) -> Record`, `records -> list[Record]`, `messages -> list[str]`, `text -> str`, `first() -> Record`, `last() -> Record`, `clear() -> None`.
  - `_capture(log: Logger = logger) -> Iterator[PlainlogCapture]` context manager.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pytest_plugin.py`:

```python
from __future__ import annotations

import pytest

from plainlog import logger
from plainlog._base import Record
from plainlog._logger import LEVEL_NOTSET
from plainlog.pytest_plugin import PlainlogCapture, _capture


def test_capture_is_a_processor() -> None:
    capture = PlainlogCapture()
    record: Record = {"msg": "x"}

    assert capture(record) is record
    assert capture.records == [record]


def test_capture_context_isolates_and_restores() -> None:
    previous_level = logger._core.min_level_no

    with _capture() as capture:
        logger.info("inside")
        assert [record["msg"] for record in capture.records] == ["inside"]
        assert logger._core.processors == (capture,)
        assert logger._core.min_level_no == LEVEL_NOTSET

    assert logger._core.processors == ()
    assert logger._core.min_level_no == previous_level


def test_records_flush_pending() -> None:
    with _capture() as capture:
        logger.info("pending")
        assert [record["msg"] for record in capture.records] == ["pending"]


def test_first_and_last() -> None:
    with _capture() as capture:
        logger.info("a")
        logger.warning("b")
        assert capture.first()["msg"] == "a"
        assert capture.last()["msg"] == "b"


def test_first_and_last_raise_when_empty() -> None:
    with _capture() as capture:
        with pytest.raises(IndexError):
            capture.first()
        with pytest.raises(IndexError):
            capture.last()


def test_clear() -> None:
    with _capture() as capture:
        logger.info("x")
        assert capture.records
        capture.clear()
        assert capture.records == []


def test_text_and_messages_default_to_raw_msg() -> None:
    with _capture() as capture:
        logger.info("one")
        logger.warning("two")
        assert capture.messages == ["one", "two"]
        assert capture.text == "one\ntwo"


def test_text_is_empty_without_records() -> None:
    with _capture() as capture:
        assert capture.text == ""


def test_text_with_non_string_msg() -> None:
    capture = PlainlogCapture()
    record: Record = {"msg": {"a": 1}}

    capture(record)

    assert capture.records == [record]
    assert capture.text == "{'a': 1}"


def test_captures_child_logger_fields() -> None:
    with _capture() as capture:
        log = logger.new("child").bind(request_id="abc")
        log.info("hi")
        record = capture.first()
        assert record["name"] == "child"
        assert record["request_id"] == "abc"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_pytest_plugin.py -x -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'plainlog.pytest_plugin'`

- [ ] **Step 3: Write minimal implementation**

Create `src/plainlog/pytest_plugin.py`:

```python
"""Pytest plugin providing the ``plog`` capture fixture for plainlog.

Importing this module requires pytest. The plainlog core never imports it.
"""

from __future__ import annotations

import contextlib
from typing import Callable, Iterator, Optional

from ._base import Record
from ._logger import LEVEL_NOTSET, Logger, logger
from .processors import get_formatted_message


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


@contextlib.contextmanager
def _capture(log: Logger = logger) -> Iterator[PlainlogCapture]:
    """Install isolated capture for the duration of the ``with`` block.

    The previous level is restored on exit. The previous processor pipeline is
    not restored, because swapping it out has already closed any closable
    processors.
    """
    previous_level = log._core.min_level_no
    capture = PlainlogCapture(log)
    log.configure(processors=[capture], level=LEVEL_NOTSET)
    try:
        yield capture
    finally:
        log.configure(processors=(), level=previous_level)
        capture.clear()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_pytest_plugin.py -x -v`
Expected: PASS (all 10 tests)

- [ ] **Step 5: Commit (requires user approval)**

```bash
git add src/plainlog/pytest_plugin.py tests/test_pytest_plugin.py
git commit -m "add plainlog capture object"
```

---

### Task 3: Level control on `PlainlogCapture`

**Files:**
- Modify: `src/plainlog/pytest_plugin.py`
- Test: `tests/test_pytest_plugin.py`

**Interfaces:**
- Consumes: existing `Logger.configure(level=...)`, `Core.min_level_no`.
- Produces: `PlainlogCapture.set_level(level: str | int) -> None`, `PlainlogCapture.at_level(level: str | int)` context manager.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_pytest_plugin.py`:

```python
def test_set_level_filters_records() -> None:
    with _capture() as capture:
        capture.set_level("WARNING")
        logger.info("hidden")
        logger.warning("shown")
        assert [record["msg"] for record in capture.records] == ["shown"]


def test_set_level_rejects_unknown_level() -> None:
    with _capture() as capture:
        with pytest.raises(ValueError):
            capture.set_level("NOPE")


def test_at_level_restores_previous_level() -> None:
    with _capture() as capture:
        capture.set_level("WARNING")
        with capture.at_level("DEBUG"):
            logger.debug("visible")
        logger.debug("hidden")
        assert [record["msg"] for record in capture.records] == ["visible"]


def test_at_level_restores_on_exception() -> None:
    with _capture() as capture:
        capture.set_level("WARNING")
        with pytest.raises(RuntimeError):
            with capture.at_level("DEBUG"):
                raise RuntimeError("boom")
        logger.debug("hidden")
        assert capture.records == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_pytest_plugin.py -k "level" -x -v`
Expected: FAIL with `AttributeError: 'PlainlogCapture' object has no attribute 'set_level'`

- [ ] **Step 3: Write minimal implementation**

In `src/plainlog/pytest_plugin.py`, add `Union` to the typing import:

```python
from typing import Callable, Iterator, Optional, Union
```

Then add these methods to `PlainlogCapture`, after `_format()`:

```python
    def set_level(self, level: Union[str, int]) -> None:
        """Set the Core's minimum level (process-wide).

        Args:
            level: Level name (e.g. ``"INFO"``) or numeric level.
        """
        self._logger.configure(level=level)

    @contextlib.contextmanager
    def at_level(self, level: Union[str, int]) -> Iterator[None]:
        """Temporarily set the Core's minimum level for a ``with`` block.

        Args:
            level: Level name (e.g. ``"INFO"``) or numeric level.
        """
        previous = self._logger._core.min_level_no
        self._logger.configure(level=level)
        try:
            yield
        finally:
            self._logger.configure(level=previous)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_pytest_plugin.py -x -v`
Expected: PASS

- [ ] **Step 5: Commit (requires user approval)**

```bash
git add src/plainlog/pytest_plugin.py tests/test_pytest_plugin.py
git commit -m "add level control to capture"
```

---

### Task 4: Opt-in formatter on `PlainlogCapture`

**Files:**
- Modify: `src/plainlog/pytest_plugin.py`
- Test: `tests/test_pytest_plugin.py`

**Interfaces:**
- Consumes: `SimpleFormatter`, existing `PlainlogCapture._format`.
- Produces: `PlainlogCapture.set_formatter(formatter: str | Callable[[Record], str] | None) -> None`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_pytest_plugin.py`:

```python
def test_set_formatter_with_string() -> None:
    with _capture() as capture:
        capture.set_formatter("{level_name}: {message}")
        logger.info("hi")
        assert capture.text == "INFO: hi"


def test_set_formatter_with_callable() -> None:
    with _capture() as capture:
        capture.set_formatter(lambda record: str(record["msg"]).upper())
        logger.info("hi")
        assert capture.messages == ["HI"]


def test_set_formatter_none_resets() -> None:
    with _capture() as capture:
        capture.set_formatter("{message}")
        capture.set_formatter(None)
        logger.info("hi")
        assert capture.text == "hi"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_pytest_plugin.py -k "formatter" -x -v`
Expected: FAIL with `AttributeError: 'PlainlogCapture' object has no attribute 'set_formatter'`

- [ ] **Step 3: Write minimal implementation**

In `src/plainlog/pytest_plugin.py`, add `SimpleFormatter` to the processors import:

```python
from .processors import SimpleFormatter, get_formatted_message
```

Then add to `PlainlogCapture`, after `at_level()`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_pytest_plugin.py -x -v`
Expected: PASS

- [ ] **Step 5: Commit (requires user approval)**

```bash
git add src/plainlog/pytest_plugin.py tests/test_pytest_plugin.py
git commit -m "add capture formatter option"
```

---

### Task 5: `plog` fixture and pytest entry point

**Files:**
- Modify: `src/plainlog/pytest_plugin.py`
- Modify: `pyproject.toml`
- Test: `tests/test_pytest_plugin.py`

**Interfaces:**
- Consumes: `_capture()` (Task 2).
- Produces: pytest fixture `plog` yielding `PlainlogCapture`; `pytest11` entry point `plainlog = "plainlog.pytest_plugin"`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_pytest_plugin.py`:

```python
def test_plog_fixture_captures(plog: PlainlogCapture) -> None:
    logger.info("hello")
    assert [record["msg"] for record in plog.records] == ["hello"]


def test_plog_fixture_captures_all_levels(plog: PlainlogCapture) -> None:
    logger.debug("debug")
    assert logger._core.min_level_no == LEVEL_NOTSET
    assert [record["msg"] for record in plog.records] == ["debug"]


def test_records_before_fixture_setup_are_not_captured(
    request: pytest.FixtureRequest,
) -> None:
    logger.info("before")
    plog = request.getfixturevalue("plog")
    logger.info("after")
    assert [record["msg"] for record in plog.records] == ["after"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_pytest_plugin.py -k "fixture or before_fixture" -x -v`
Expected: FAIL with `fixture 'plog' not found`

- [ ] **Step 3: Write minimal implementation**

In `src/plainlog/pytest_plugin.py`, append:

```python
@pytest.fixture
def plog() -> Iterator[PlainlogCapture]:
    """Capture plainlog records for the duration of the test."""
    with _capture() as capture:
        yield capture
```

In `pyproject.toml`, add after `[project.urls]` (or next to the other
`[project.*]` tables):

```toml
[project.entry-points.pytest11]
plainlog = "plainlog.pytest_plugin"
```

- [ ] **Step 4: Re-sync and run tests to verify they pass**

Run: `uv sync && uv run pytest tests/test_pytest_plugin.py -x -v`
Expected: PASS (fixture resolves through the entry point)

If the fixture is still reported missing, run:
`uv run --reinstall-package plainlog pytest tests/test_pytest_plugin.py -x -v`

- [ ] **Step 5: Commit (requires user approval)**

```bash
git add src/plainlog/pytest_plugin.py pyproject.toml tests/test_pytest_plugin.py
git commit -m "add plog pytest fixture"
```

---

### Task 6: Fresh-session integration test

**Files:**
- Modify: `tests/conftest.py`
- Test: `tests/test_pytest_plugin.py`

**Interfaces:**
- Consumes: `pytest11` entry point (Task 5); `pytester` fixture.
- Produces: an end-to-end test proving a clean pytest run auto-loads the plugin.

- [ ] **Step 1: Enable `pytester`**

In `tests/conftest.py`, add directly under the imports:

```python
pytest_plugins = ["pytester"]
```

- [ ] **Step 2: Write the failing test**

Append to `tests/test_pytest_plugin.py`:

```python
def test_plog_is_available_in_fresh_session(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        """
        from plainlog import logger


        def test_generated(plog):
            logger.info("generated")
            assert [record["msg"] for record in plog.records] == ["generated"]
        """
    )

    result = pytester.runpytest()

    result.assert_outcomes(passed=1)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_pytest_plugin.py::test_plog_is_available_in_fresh_session -x -v`
Expected: FAIL with `fixture 'pytester' not found` (step 1 not applied) — then, after step 1, FAIL if the entry point is not installed.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_pytest_plugin.py::test_plog_is_available_in_fresh_session -x -v`
Expected: PASS

- [ ] **Step 5: Commit (requires user approval)**

```bash
git add tests/conftest.py tests/test_pytest_plugin.py
git commit -m "test plog in fresh pytest session"
```

---

### Task 7: Documentation

**Files:**
- Create: `docs/testing.md`
- Modify: `docs/logger.md`, `docs/changelog.md`, `zensical.toml`, `AGENTS.md`
- Test: `tests/test_examples.py` (existing; must still pass)

**Interfaces:**
- Consumes: `plog` fixture (Task 5), `plainlog.pytest_plugin.PlainlogCapture`, `logger.flush()` (Task 1).
- Produces: user-facing docs.

- [ ] **Step 1: Create `docs/testing.md`**

```markdown
# Testing

plainlog ships a pytest plugin that is enabled automatically once plainlog is
installed, providing the `plog` fixture — a small caplog-like capture object.

## Quick start

The fixture swaps in an isolated capture pipeline for the test, then clears it.
Records are processed on a background thread, so `plog.records` flushes before
returning.

```python
from plainlog import logger


def test_greeting(plog):
    logger.info("hello")
    assert [record["msg"] for record in plog.records] == ["hello"]
```

## Asserting on records

`plog.records` is a list of the raw record dicts. `first()` and `last()` are
convenient shortcuts.

```python
def test_fields(plog):
    log = logger.new("child").bind(request_id="abc")
    log.warning("careful")

    record = plog.last()
    assert record["name"] == "child"
    assert record["level_name"] == "WARNING"
    assert record["request_id"] == "abc"
```

## Formatted text

`.text` joins the raw messages with newlines. Pass a format string or a callable
to `set_formatter()` for formatted output.

```python
def test_text(plog):
    plog.set_formatter("{level_name}: {message}")
    logger.info("ready")
    assert plog.text == "INFO: ready"
```

## Controlling the level

The Core level is process-wide, so `set_level()` and `at_level()` affect every
logger while active.

```python
def test_levels(plog):
    plog.set_level("WARNING")
    logger.info("hidden")

    with plog.at_level("DEBUG"):
        logger.debug("visible")

    assert [record["msg"] for record in plog.records] == ["visible"]
```

## Flushing manually

`logger.flush()` blocks until every queued record has been processed.

```python
from plainlog import logger

logger.info("processing")
logger.flush()
```

## caplog vs plog

| pytest `caplog` | plainlog `plog` |
|-----------------|-----------------|
| `caplog.records` | `plog.records` (raw record dicts) |
| `caplog.text` | `plog.text` |
| `caplog.messages` | `plog.messages` |
| `caplog.set_level(...)` | `plog.set_level(...)` |
| `caplog.at_level(...)` | `plog.at_level(...)` |
| `caplog.clear()` | `plog.clear()` |

Because capture is isolated, `plog` replaces the app's real processor pipeline
for the test and does not restore it; tests that need real handlers should not
rely on `plog`.
```

- [ ] **Step 2: Document `Logger.flush()` in `docs/logger.md`**

Insert a new section before `## API Reference`:

```markdown
---

## Flushing

Records are processed on a background thread. `flush()` blocks until every
record queued so far has been processed — useful before reading output.

```python
from plainlog import logger

logger.info("processing")
logger.flush()
```
```

- [ ] **Step 3: Update `docs/changelog.md`**

Add above `## 0.8.0 - 2026-09-27`:

```markdown
## Unreleased

### Added

- `plainlog.pytest_plugin` — an auto-registered pytest plugin providing the
  `plog` fixture, a caplog-like capture object.
- `Logger.flush()` — block until queued records have been processed.
```

- [ ] **Step 4: Add the docs page to navigation**

In `zensical.toml`, change the `nav` list to include testing before Changelog:

```toml
nav = [
  { "Get started" = "index.md" },
  { "Logger" = "logger.md" },
  { "Configuration" = "configuration.md" },
  { "Processors & Handlers" = "processors.md" },
  { "Base Types" = "base.md" },
  { "Plainlog vs stdlib" = "comparison_to_stdlib.md" },
  { "Testing" = "testing.md" },
  { "Changelog" = "changelog.md" },
]
```

- [ ] **Step 5: Update `AGENTS.md`**

Replace this line in the Docs section:

```
- Doc pages: `docs/index.md`, `docs/logger.md`, `docs/configuration.md`, `docs/processors.md`, `docs/base.md`, `docs/comparison_to_stdlib.md`, `docs/changelog.md`.
```

with:

```
- Doc pages: `docs/index.md`, `docs/logger.md`, `docs/configuration.md`, `docs/processors.md`, `docs/base.md`, `docs/comparison_to_stdlib.md`, `docs/testing.md`, `docs/changelog.md`.
```

Then add this row at the end of the Key files table (after the `_base.py` row):

```markdown
| `src/plainlog/pytest_plugin.py` | Auto-registered pytest plugin: `plog` capture fixture |
```

- [ ] **Step 6: Run the docs-example tests**

Run: `uv run pytest tests/test_examples.py -x -v`
Expected: PASS (all code blocks execute cleanly)

- [ ] **Step 7: Commit (requires user approval)**

```bash
git add docs/testing.md docs/logger.md docs/changelog.md zensical.toml AGENTS.md
git commit -m "document pytest plugin"
```

---

### Task 8: Full verification and graph update

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `make test`
Expected: PASS

- [ ] **Step 2: Run coverage**

Run: `make test-cov`
Expected: 100% coverage; if any new lines are missing, add tests in
`tests/test_pytest_plugin.py` and re-run.

- [ ] **Step 3: Lint and type-check**

Run: `make lint`
Expected: no errors.

Run: `make type-check`
Expected: no errors.

- [ ] **Step 4: Update the knowledge graph**

Run: `graphify update .`
Expected: completes without error.

- [ ] **Step 5: Report**

Summarize which files changed and paste the final `make test`, `make lint`,
`make type-check`, and `make test-cov` results.
