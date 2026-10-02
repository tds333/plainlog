# Logger

The `Logger` class is the primary interface for creating log records. In most
cases you use the pre-configured module-level instance.

---

## Getting a Logger

```python
from plainlog import logger

log = logger.new()
log.info("hello world")
```

The module-level `logger` is a `Logger` bound to the global Core singleton
with name ``"root"``. It is automatically configured on import — by default
it uses the ``"default"`` profile (writes to stdout).

Prefer creating one child logger per module with `logger.new()` (it
auto-detects the module name); the root `logger` is mainly the shared entry
point and a factory for child loggers.

---

## Basic Logging

```python
from plainlog import logger

log = logger.new()  # auto-named after the current module

log.debug("debug message")
log.info("info message")
log.warning("warning message")
log.error("error message")
log.critical("critical message")
```

Each level method accepts a message and optional keyword arguments that are
merged into the log record as top-level fields (for example ``record["user"]``).

### Log with a specific level

```python
from plainlog import logger

log = logger.new()
log.log("INFO", "explicit level")
log.log(20, "level as int")
```

### Callable form

A `Logger` is also callable. `log(level, msg, **kwargs)` behaves like
`log.log()` but returns a ``bool``: ``True`` if the record was accepted by
the Core's processor pipeline, ``False`` if it was dropped (no processors
configured, or below the minimum level).

```python
from plainlog import logger

log = logger.new()
accepted = log("INFO", "positional form")
also_accepted = log(level="WARNING", msg="keyword form")
```

### Log with exception info

```python
from plainlog import logger

log = logger.new()

try:
    1 / 0
except ZeroDivisionError:
    log.exception("something went wrong")
```

---

## Configuration

### Using a profile

```python
from plainlog import logger
from plainlog.configure import apply_log_profile

apply_log_profile("develop", level="DEBUG")
log = logger.new()
log.info("now with colors and caller info")
```

### Direct processor setup

```python
from plainlog import logger
from plainlog.processors import SimpleFormatter, Stream

logger.configure(processors=[SimpleFormatter(), Stream()])
```

See [Processors, Formatters & Handlers](processors.md) for everything available.

---

## Binding Variables

Use `bind()` to create a child logger with
additional static key-value pairs attached to every record.

```python
from plainlog import logger

log = logger.new().bind(user="alice", request_id="abc-123")
log.info("user action")
```

Use `unbind()` to remove keys.

```python
from plainlog import logger

log = logger.new().bind(user="alice", request_id="abc-123")
log2 = log.unbind("request_id")
log2.info("without request_id")
```

---

## Context Variables

Use `contextualize()` to attach variables for the
duration of a block.

```python
from plainlog import logger

log = logger.new()
with log.contextualize(request_id="xyz"):
    log.info("inside context")
```

The context is thread-safe (backed by ``ContextVar``) and works correctly in
async code.

For manual control, `context()` sets the variables and returns a token that
`reset_context()` restores:

```python
from plainlog import logger

log = logger.new()
token = log.context(request_id="xyz")
try:
    log.info("inside context")
finally:
    log.reset_context(token)
log.info("after context")
```

---

## Child Loggers

Use `new()` to create a child logger. The name
is auto-detected from the caller's module and function.

```python
from plainlog import logger

log = logger.new()
```

To explicitly derive the logger name from the current module, pass
``__name__``:

```python
from plainlog import logger

log = logger.new(__name__)
log.info("logged with the module name as logger name")
```

---

## Flushing

Records are processed on a background thread. `flush()` blocks until every
record queued so far has been processed — useful before reading output.

```python
from plainlog import logger

logger.info("processing")
logger.flush()
```

---

## API Reference

### Logger

::: plainlog._logger.Logger

### Module-Level Instance

::: plainlog.logger

### apply_log_profile

::: plainlog.configure.apply_log_profile
