# Processors, Formatters & Handlers

Processors, formatters and handlers all live in `plainlog.processors`:

- **Processors** transform a log record in the Core's background thread.
- **Formatters** are processors that set the formatted ``message`` on a record.
- **Handlers** are processors that perform output.

Every processor is a callable with the signature `__call__(record)` and
may optionally provide a `close()` method for cleanup:

- **`__call__(record)`** — runs in the Core's background thread after
  dequeueing. This is where I/O happens. Return a falsy value (e.g. `{}`)
  to stop processing for that record.
- **`close()`** — cleanup resources (close files, wait for futures, etc.).

Processors are configured as a list and run in order. A typical setup is a
formatter followed by a handler:

```python
from plainlog import logger
from plainlog.processors import SimpleFormatter, Stream

logger.configure(processors=[SimpleFormatter(), Stream()])
```

## Built-in Processors

### Formatters

| Formatter | Description |
|-----------|-------------|
| [`SimpleFormatter`](#simpleformatter) | Minimal single-line format |
| [`DefaultFormatter`](#defaultformatter) | Compact format with time and extras |
| [`JsonFormatter`](#jsonformatter) | Serializes a record as JSON |

### Output Handlers

| Handler | Description |
|---------|-------------|
| [`Stream`](#stream) | Writes to any file-like stream |
| [`FileWriter`](#filewriter) | Writes to a file, supports rotation watching |
| [`AsyncBridge`](#asyncbridge) | Base class for async integrations |

### Composition Handlers

| Handler | Description |
|---------|-------------|
| [`SubProcessor`](#subprocessor) | Runs a nested processor pipeline on a record copy |
| [`FingersCrossed`](#fingerscrossed) | Buffers until a threshold level triggers a flush |
| [`WrapStandardHandler`](#wrapstandardhandler) | Bridges plainlog records to stdlib handlers |

## Usage

### Formatter and Stream

```python
from plainlog import logger
from plainlog.processors import JsonFormatter, Stream

logger.configure(processors=[JsonFormatter(), Stream()])
```

### FingersCrossed — Buffer Until Error

```python
from plainlog import logger
from plainlog.processors import FingersCrossed, SimpleFormatter, Stream

# Buffer up to 100 records, flush everything on ERROR (level 40)
handler = FingersCrossed(
    Stream(),
    action_level=40,
    buffer_size=100,
)
logger.configure(processors=[SimpleFormatter(), handler])
```

### AsyncBridge Subclass

```python
import asyncio
from plainlog.processors import AsyncBridge

class MyAsyncBridge(AsyncBridge):
    async def write(self, message):
        # e.g. send to a network sink
        await asyncio.sleep(0)
        print(message)
```

## API Reference

### Stream

::: plainlog.processors.Stream

### SubProcessor

::: plainlog.processors.SubProcessor

### WrapStandardHandler

::: plainlog.processors.WrapStandardHandler

### FingersCrossed

::: plainlog.processors.FingersCrossed

### FileWriter

::: plainlog.processors.FileWriter

### AsyncBridge

::: plainlog.processors.AsyncBridge

### SimpleFormatter

::: plainlog.processors.SimpleFormatter

### DefaultFormatter

::: plainlog.processors.DefaultFormatter

### JsonFormatter

::: plainlog.processors.JsonFormatter
