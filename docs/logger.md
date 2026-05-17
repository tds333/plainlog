# Logger

The `Logger` class is the primary interface for creating log records. In most
cases you use the pre-configured module-level instance.

---

## Module-Level Logger

```python
from plainlog import logger

logger.info("hello world")
```

The module-level `logger` is a `Logger` bound to the
global Core singleton with name ``"root"``. It is automatically configured on
import — by default it uses the ``"default"`` profile (writes to stdout).

---

## Basic Logging

```python
from plainlog import logger

logger.debug("debug message")
logger.info("info message")
logger.warning("warning message")
logger.error("error message")
logger.critical("critical message")
```

Each level method accepts a message and optional keyword arguments that are
stored in the record's ``kwargs`` dict.

### Log with a specific level

```python
from plainlog import logger

logger.log("INFO", "explicit level")
logger.log(20, "level as int")
```

### Log with exception info

```python
import sys
from plainlog import logger

try:
    1 / 0
except ZeroDivisionError:
    logger.exception("something went wrong")
```

---

## Configuration

### Using a profile

```python
from plainlog import logger
from plainlog.configure import apply_log_profile

apply_log_profile("develop", level="DEBUG")
logger.info("now with colors and caller info")
```

### Direct handler setup

```python
from plainlog import logger
from plainlog.handlers import StreamHandler

logger.configure(handler=StreamHandler())
```

See [Handlers](handlers.md) for all available handlers.

---

## Binding Extra Variables

Use `bind()` to create a child logger with
additional static key-value pairs attached to every record.

```python
from plainlog import logger

log = logger.bind(user="alice", request_id="abc-123")
log.info("user action")
```

Use `unbind()` to remove keys.

```python
from plainlog import logger

log = logger.bind(user="alice", request_id="abc-123")
log2 = log.unbind("request_id")
log2.info("without request_id")
```

---

## Context Variables

Use `contextualize()` to attach variables for the
duration of a block.

```python
from plainlog import logger

with logger.contextualize(request_id="xyz"):
    logger.info("inside context")
```

The context is thread-safe (backed by ``ContextVar``) and works correctly in
async code.

---

## Child Loggers

Use `new()` to create a child logger. The name
is auto-detected from the caller's module and function.

```python
from plainlog import logger

child = logger.new()
```

---

## API Reference

### Logger

::: plainlog._logger.Logger

### Module-Level Instance

::: plainlog.logger

### apply_log_profile

::: plainlog.configure.apply_log_profile
