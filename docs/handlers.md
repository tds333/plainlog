# Handlers

Handlers are responsible for the actual output of log records. Each handler
implements the [`HandlerProtocol`](base.md#handlerprotocol) with three methods:

- **`preprocess(record)`** — runs in the application thread before the record
  is enqueued to the Core. Use this to enrich or filter records early.
- **`process(record)`** — runs in the Core's background thread after
  dequeueing. This is where I/O happens.
- **`close()`** — cleanup resources (close files, wait for futures, etc.).

If any method returns a falsy value (e.g. `{}`), processing stops for that
record.

## Built-in Handlers

### Output Handlers

| Handler | Description |
|---------|-------------|
| [`StreamHandler`](#streamhandler) | Writes to any file-like stream |
| [`DefaultHandler`](#defaulthandler) | stdout with a compact default format |
| [`ConsoleHandler`](#consolehandler) | Colorized output for development |
| [`DevelopHandler`](#develophandler) | ConsoleHandler + caller info enrichment |
| [`JsonHandler`](#jsonhandler) | One JSON object per record |
| [`FileHandler`](#filehandler) | Writes to a file, supports rotation watching |
| [`AsyncHandler`](#asynchandler) | Base class for async integrations |

### Composition Handlers

| Handler | Description |
|---------|-------------|
| [`ProcessingHandler`](#processinghandler) | Wraps a handler with preprocessor/processor pipelines |
| [`CollectHandler`](#collecthandler) | Dispatches to multiple sub-handlers |
| [`FingersCrossedHandler`](#fingerscrossedhandler) | Buffers until a threshold level triggers a flush |
| [`WrapStandardHandler`](#wrapstandardhandler) | Bridges plainlog records to stdlib handlers |

## Usage

### Basic StreamHandler

```python
from plainlog import logger
from plainlog.handlers import StreamHandler

logger.configure(handler=StreamHandler())
```

### ProcessingHandler with Callers Info

```python
from plainlog import logger
from plainlog.handlers import ProcessingHandler, ConsoleHandler
from plainlog.processors import add_caller_info

handler = ProcessingHandler(
    preprocessors=[add_caller_info],
    handler=ConsoleHandler(colors=True),
)
logger.configure(handler=handler)
```

### CollectHandler — Write to Console and File

```python
from plainlog import logger
from plainlog.handlers import CollectHandler, ConsoleHandler, FileHandler

handler = CollectHandler([
    ConsoleHandler(),
    FileHandler("app.log"),
])
logger.configure(handler=handler)
```

### FingersCrossedHandler — Buffer Until Error

```python
from plainlog import logger
from plainlog.handlers import FingersCrossedHandler, ConsoleHandler

# Buffer up to 100 records, flush everything on ERROR (level 40)
handler = FingersCrossedHandler(
    ConsoleHandler(),
    action_level=40,
    buffer_size=100,
)
logger.configure(handler=handler)
```

### AsyncHandler Subclass

```python
import asyncio
from plainlog.handlers import AsyncHandler

class MyAsyncHandler(AsyncHandler):
    async def write(self, message):
        # e.g. send to a network sink
        await asyncio.sleep(0)
        print(message)
```

## API Reference

### BaseHandler

::: plainlog.handlers.BaseHandler

### ProcessingHandler

::: plainlog.handlers.ProcessingHandler

### CollectHandler

::: plainlog.handlers.CollectHandler

### StreamHandler

::: plainlog.handlers.StreamHandler

### DefaultHandler

::: plainlog.handlers.DefaultHandler

### ConsoleHandler

::: plainlog.handlers.ConsoleHandler

### DevelopHandler

::: plainlog.handlers.DevelopHandler

### WrapStandardHandler

::: plainlog.handlers.WrapStandardHandler

### JsonHandler

::: plainlog.handlers.JsonHandler

### FingersCrossedHandler

::: plainlog.handlers.FingersCrossedHandler

### FileHandler

::: plainlog.handlers.FileHandler

### AsyncHandler

::: plainlog.handlers.AsyncHandler
