# plainlog pytest plugin — design

> **Revision 2026-10-02 — superseded by an importable module.**
> The shipped design is an importable `plainlog.testing` module
> (`capture_logs()` + `PlainlogCapture`) with **no pytest plugin and no
> `pytest11` entry point**. `Logger.flush()` stands. The plugin-specific
> sections below (entry-point registration, a package-shipped `plainlog` fixture,
> the `make test-cov` workaround) no longer apply; see `docs/testing.md` for
> the final API.

Date: 2026-10-02
Status: Draft (awaiting user review)

## Context

plainlog has no pytest integration and no `caplog`-style capture. The project's
own tests capture logs with a private convention:

- `tests/conftest.py` defines `DummyHandler`, a processor that appends records
  to a list, and a `thandler` fixture that installs it.
- Records are produced by a background `Core` thread, so tests must call the
  private `logger_core.wait_for_processed()` before reading — `DummyHandler`
  hides this inside its `.records` property.

External users have no supported way to assert on plainlog output. This design
adds a bundled pytest plugin and one small public API method so tests can do:

```python
def test_greeting(plog):
    logger.info("hello {name}", name="world")
    assert plog.records[-1]["msg"] == "hello {name}"
    assert "hello world" in plog.text
```

## Goals

- A caplog-like pytest fixture (`plog`) available automatically once plainlog is
  installed.
- Expose plainlog's structured `Record` dicts, plus convenient formatted text.
- Hide the background-thread synchronization behind a public `logger.flush()`.
- Keep the plainlog core zero-dependency; only the plugin module imports pytest.
- Preserve the project's 100% coverage bar.

## Non-goals

- No stdlib `logging` bridge changes; no `logging.LogRecord` translation.
- No per-logger level control (plainlog's level is core-global).
- No live capture alongside the app's real handler pipeline.
- No separate distribution.

## Decisions (from brainstorming)

| Question | Decision |
|----------|----------|
| Fixture surface | caplog-like object: `.records`, `.text`, helpers |
| Distribution | Bundled module, auto-registered via `pytest11` entry point |
| Pipeline interaction | Isolated capture; on teardown clear processors (no restore) |
| `.text` formatting | Raw `msg` by default; opt-in formatter |
| Outgoing-processor `close()` | Accepted: app handlers are closed when `plog` swaps in |

## Public API change

Add one method to `Logger` in `src/plainlog/_logger.py`:

```python
def flush(self, timeout: float | None = None) -> None:
    """Block until the worker has processed every record queued so far."""
    self._core.wait_for_processed(timeout)
```

- `Core.wait_for_processed()` is unchanged; it remains the low-level primitive.
- No new public getters (`Logger.processors`, `Logger.level`) are added. The
  plugin lives in the same package and may read `logger._core` internals.
- `plainlog.__all__` stays `["logger"]`; the method is reached as `logger.flush()`.

## Plugin module: `src/plainlog/pytest_plugin.py`

Only this module imports `pytest`. Importing `plainlog` never imports it.

### Registration

`pyproject.toml`:

```toml
[project.entry-points.pytest11]
plainlog = "plainlog.pytest_plugin"
```

When pytest runs, the auto-registered plugin contributes the `plog` fixture.
With `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` the fixture is simply unavailable.

### `PlainlogCapture`

A callable processor object plus test-facing query API.

Processor behaviour:

- `__call__(record) -> record`: append `record` to the internal list and return
  it unchanged. Returning the record keeps it chainable if a user composes it.

Query API:

- `.records` -> `list[Record]`: calls `logger.flush()` first, then returns a
  shallow copy of the captured records. Copy prevents callers mutating state.
- `.messages` -> `list[str]`: flushed, per-record formatted strings (see
  Formatting).
- `.text` -> `str`: `"\n".join(self.messages)`.
- `.first()` -> `Record`: flushed first record. Raises `IndexError` if empty.
- `.last()` -> `Record`: flushed last record. Raises `IndexError` if empty.
- `.clear()` -> `None`: drops captured records (no flush needed).
- `.set_level(level)` -> `None`: `logger.configure(level=level)`; processors are
  left unchanged.
- `.at_level(level)`: context manager; snapshot `logger._core.min_level_no`,
  set the new level, restore on exit (including on exception).
- `.set_formatter(formatter)` -> `None`:
  - `str`: stored and applied via `SimpleFormatter(formatter)`; `.messages` use
    the resulting `formatted_message`.
  - callable `(Record) -> str`: called directly per record.
  - `None`: reset to default (raw message).

### Fixture lifecycle

Function-scoped `plog` fixture:

```python
@pytest.fixture
def plog() -> Iterator[PlainlogCapture]:
    previous_level = logger._core.min_level_no
    capture = PlainlogCapture()
    logger.configure(processors=[capture], level=NOTSET)
    try:
        yield capture
    finally:
        logger.configure(processors=())
        logger.configure(level=previous_level)
        capture.clear()
```

- Setup installs capture-only at `NOTSET` so every record is captured.
- Teardown clears processors (per the close-on-swap constraint, restoring the
  previous processors is not safe) and restores the previous level.

## Formatting

Default `.messages` entry uses `get_formatted_message(record)`:

- If a formatter already ran and set `message`/`formatted_message`, that is used.
- Otherwise it falls back to `str(record["msg"])`.

Because isolated capture replaces the pipeline, no formatter runs during a
`plog` test, so the default is the raw `msg` string. `set_formatter` lets tests
opt into formatted output without changing the app pipeline.

## Level semantics

plainlog has a single core-global minimum level (`Core._min_level_no`). Therefore:

- `plog.set_level("INFO")` affects every logger in the process until changed.
- `plog.at_level("INFO")` scopes the change to a `with` block.
- The fixture captures at `NOTSET` (all levels) by default and restores the
  previous level afterward.

Documented caveat: level changes are process-wide for the test duration.

## Interaction with the existing test suite

- The plugin is auto-registered while running plainlog's own tests, so
  `tests/test_pytest_plugin.py` can request `plog` directly.
- Existing `thandler`-based tests are unaffected; both capture mechanisms
  configure the shared core independently per test.

## Testing plan

`tests/test_pytest_plugin.py` (functions, not classes; matching repo style):

- `PlainlogCapture` as a processor: calling it appends and returns the record.
- `.records` flushes pending records (log without explicit flush, then assert).
- `.text` / `.messages` default raw-message output.
- `.first()` / `.last()` behaviour, including empty-capture `IndexError`.
- `.clear()` empties captured records.
- `.set_level()` filters lower records; `.at_level()` restores on normal and
  exceptional exit.
- `.set_formatter(str)` and `.set_formatter(callable)`; reset with `None`.
- Fixture teardown clears processors and restores the previous level.
- Integration: a `pytester` test proving end-to-end entry-point loading
  (`pytest_plugins = ["pytester"]`), asserting a generated test using `plog`
  passes.

`tests/test_logger.py`:

- `logger.flush()` returns only after queued records are processed/observable.

Quality gates: `make test` (100% coverage), `make lint`, `make type-check`.

## Documentation

- New `docs/testing.md`: using `plog`, record vs text assertions,
  `set_level`/`at_level`, custom formatter, `logger.flush()`, and a
  caplog -> plainlog mapping table.
- `zensical.toml`: add `{ "Testing" = "testing.md" }` to `[nav]`.
- `docs/logger.md`: document `logger.flush()`.
- `AGENTS.md`: add `testing.md` to the doc-page list and `pytest_plugin.py` to
  the key-files table.
- `docs/changelog.md`: add an entry.
- Code blocks must stay `pytest-examples`-safe; test-function definitions are
  not executed by the example runner, so they are acceptable. `make test`
  verifies this.

## Risks and caveats

- **Closed app handlers:** swapping in `[capture]` closes any existing closable
  processors (`Stream`, `FileWriter`, `AsyncBridge`, `SubProcessor`,
  `WrapStandardHandler`, `FingersCrossed`). `plog` therefore replaces the app
  pipeline for the remainder of the session; tests that need real handlers must
  not use `plog` mid-session unless they reconfigure.
- **Global level:** `set_level`/`at_level` are process-wide.
- **Coverage:** the new module counts toward 100%; all branches must be tested.
- **Autoload:** users with plugin autoload disabled must opt in manually.

## Files touched

| File | Change |
|------|--------|
| `src/plainlog/_logger.py` | Add `Logger.flush()` |
| `src/plainlog/pytest_plugin.py` | New plugin module + `plog` fixture |
| `pyproject.toml` | `pytest11` entry point |
| `tests/test_pytest_plugin.py` | New tests |
| `tests/test_logger.py` | `flush()` test |
| `docs/testing.md` | New doc page |
| `docs/logger.md` | `flush()` docs |
| `docs/changelog.md` | Changelog entry |
| `zensical.toml` | Nav entry |
| `AGENTS.md` | Doc list + key files |
