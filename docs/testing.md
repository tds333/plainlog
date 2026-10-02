# Testing

plainlog ships a framework-agnostic `plainlog.testing` module. It has no test
runner dependency: import `capture_logs()` and use it directly, or wrap it in a
fixture for pytest or unittest.

## Quick start

`capture_logs()` disables the configured processors while it is active and
collects every record. `records` flushes the background Core thread before
returning.

```python
from plainlog import logger
from plainlog.testing import capture_logs

with capture_logs() as logs:
    logger.info("hello")

assert logs.messages == ["hello"]
```

## Asserting on records

`logs.records` is a list of the raw record dicts. `first()` and `last()` are
convenient shortcuts.

```python
from plainlog import logger
from plainlog.testing import capture_logs

with capture_logs() as logs:
    log = logger.new("child").bind(request_id="abc")
    log.warning("careful")

record = logs.last()
assert record["name"] == "child"
assert record["level_name"] == "WARNING"
assert record["request_id"] == "abc"
```

## Formatted text

`.text` joins the raw messages with newlines. Pass a format string or a
callable to `set_formatter()` for formatted output.

```python
from plainlog import logger
from plainlog.testing import capture_logs

with capture_logs() as logs:
    logs.set_formatter("{level_name}: {message}")
    logger.info("ready")

assert logs.text == "INFO: ready"
```

## Controlling the level

The Core level is process-wide, so `set_level()` and `at_level()` affect every
logger while active.

```python
from plainlog import logger
from plainlog.testing import capture_logs

with capture_logs() as logs:
    logs.set_level("WARNING")
    logger.info("hidden")
    with logs.at_level("DEBUG"):
        logger.debug("visible")

assert [record["msg"] for record in logs.records] == ["visible"]
```

## Flushing manually

`logger.flush()` blocks until every queued record has been processed.

```python
from plainlog import logger

logger.info("processing")
logger.flush()
```

## Using with pytest

Add one fixture to your `conftest.py`:

```python
# conftest.py
import pytest

from plainlog.testing import capture_logs


@pytest.fixture
def plainlog():
    with capture_logs() as capture:
        yield capture
```

Then request `plainlog` in any test:

```python
from plainlog import logger


def test_greeting(plainlog):
    logger.info("hello")
    assert [record["msg"] for record in plainlog.records] == ["hello"]


def test_levels(plainlog):
    plainlog.set_level("WARNING")
    logger.info("hidden")
    logger.warning("shown")
    assert [record["msg"] for record in plainlog.records] == ["shown"]
```

`plainlog` is a `PlainlogCapture`, so every method below is available: `records`,
`messages`, `text`, `first()`, `last()`, `clear()`, `set_level()`,
`at_level()`, and `set_formatter()`.

## Using with unittest

`capture_logs()` is an ordinary context manager, so it also works in
`unittest.TestCase` methods. Wrap each test:

```python
import unittest

from plainlog import logger
from plainlog.testing import capture_logs


class TestGreeting(unittest.TestCase):
    def test_greeting(self):
        with capture_logs() as logs:
            logger.info("hello")
        self.assertEqual(logs.messages, ["hello"])

    def test_levels(self):
        with capture_logs() as logs:
            logs.set_level("WARNING")
            logger.info("hidden")
            logger.warning("shown")
        self.assertEqual(logs.messages, ["shown"])
```

To share one capture across all tests in a case, install it in `setUp()` and
tear it down with `addCleanup()`:

```python
import unittest

from plainlog import logger
from plainlog.testing import capture_logs


class TestWithSetup(unittest.TestCase):
    def setUp(self):
        self._capture = capture_logs()
        self.logs = self._capture.__enter__()
        self.addCleanup(self._capture.__exit__, None, None, None)

    def test_records(self):
        logger.info("hello")
        self.assertEqual(self.logs.messages, ["hello"])
```

## caplog vs capture_logs

| pytest `caplog` | plainlog `capture_logs` |
|-----------------|-------------------------|
| `caplog.records` | `logs.records` (raw record dicts) |
| `caplog.text` | `logs.text` |
| `caplog.messages` | `logs.messages` |
| `caplog.set_level(...)` | `logs.set_level(...)` |
| `caplog.at_level(...)` | `logs.at_level(...)` |
| `caplog.clear()` | `logs.clear()` |

Because capture is isolated, `capture_logs()` replaces the app's real processor
pipeline for the duration of the block and does not restore it; tests that need
real handlers should not rely on it.
