# Handlers

Handlers are responsible for the actual output of log records. Each handler
implements the [`HandlerProtocol`](base.md#handlerprotocol) with two methods:

- **`__call__(record)`** — runs in the Core's background thread after
  dequeueing. This is where I/O happens. Return a falsy value (e.g. `{}`)
  to stop processing for that record.
- **`close()`** — cleanup resources (close files, wait for futures, etc.).

## Built-in Handlers

### Output Handlers

| Handler | Description |
|---------|-------------|
| [`StreamHandler`](#streamhandler) | Writes to any file-like stream |
| [`DefaultHandler`](#defaulthandler) | stdout with a compact default format |
| [`ConsoleHandler`](#consolehandler) | Colorized output for development |
| [`JsonHandler`](#jsonhandler) | One JSON object per record |
| [`FileHandler`](#filehandler) | Writes to a file, supports rotation watching |
| [`AsyncHandler`](#asynchandler) | Base class for async integrations |

### Composition Handlers

| Handler | Description |
|---------|-------------|
| [`ProcessingHandler`](#processinghandler) | Dispatches to a processor/handler pipeline |
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

handler = ProcessingHandler([ConsoleHandler(colors=True)])
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

### StreamHandler

::: plainlog.handlers.StreamHandler

### DefaultHandler

::: plainlog.handlers.DefaultHandler

### ConsoleHandler

::: plainlog.handlers.ConsoleHandler

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
