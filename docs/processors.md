# Processors, Formatters & Handlers

Processors live in `plainlog.processors`:

- **Processors** transform a log record in the Core's background thread.
- **Formatters** are processors that render a record into a string, stored in
  ``record["formatted_message"]``.
- **Handlers** are processors that perform output.

But overall they are simply processors with the same interface.
Naming is just there to clarify what they do.

Every processor is a callable with the signature `__call__(record: Record) -> Record` and
may optionally provide a `close()` method for cleanup:

- **`__call__(record: Record) -> Record`** — runs in the Core's background thread after
  dequeueing. This is where I/O happens. Return an empty dict `{}`
  to stop processing for that record.
- **`close()`** — cleanup resources (close files, wait for futures, etc.). Optional.

Processors are configured as a Sequence and run in order. A typical setup is a
formatter followed by a handler:

```python
from plainlog import configure_log
from plainlog.processors import SimpleFormatter, Stream

configure_log(processors=[SimpleFormatter(), Stream()])
```

## Built-in Processors

### Formatters

| Formatter | Description |
|-----------|-------------|
| [`SimpleFormatter`](#simpleformatter) | Single-line format with timestamp and level |
| [`JsonFormatter`](#jsonformatter) | Serializes a record as JSON string |

!!! note
    With a custom `fmt`, any field on the record can be used as a placeholder
    (for example `{name}`, `{level_name}`, or a user-supplied field). There is
    no special `extra` field — keyword arguments are stored directly on the
    record — so an unknown placeholder such as `{extra}` raises `KeyError`.

!!! note
    `JsonFormatter` serializes a fixed set of keys (`message`, `name`,
    `created`, `level_name`, `level_no`, `process_id`, `process_name`) plus any
    keys named in its `additional_keys` argument. User-supplied fields are
    **not** included automatically; list them in `additional_keys` or use a
    formatter that renders the whole record.

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

### Filters & Utilities

| Processor | Description |
|-----------|-------------|
| `format_message` | Fills ``record["message"]`` from ``msg`` and the record's fields |
| `print_processor_error` | Prints a record's processor error to stderr |
| `redact_fields(*fields, mask="***REDACTED***")` | Masks exact record keys (case-insensitive, recurses into nested dicts and lists) |
| `redact_by_pattern(*patterns, mask="***REDACTED***")` | Masks record keys containing a substring (case-insensitive, recurses into nested dicts and lists) |
| `filter_None` | Drops records whose ``name`` is ``None`` |
| `filter_all` | Drops every record |
| `filter_by_name("parent")` | Drops records whose name starts with ``parent`` |
| `allow_by_name("parent")` | Keeps only records whose name starts with ``parent`` |
| `filter_by_level(level_per_module)` | Per-module minimum levels; ``False`` blocks a module |
| `FilterList(blacklist, whitelist=None)` | Name-based deny/allow list processor |
| `WhitelistLevel(whitelist)` | Per-module level allow list |
| `ConsoleRenderer` | Developer-friendly colored line renderer |

All of these are available from ``plainlog.processors``.

## Usage

### Formatter and Stream

```python
from plainlog import configure_log
from plainlog.processors import JsonFormatter, Stream

configure_log(processors=[JsonFormatter(), Stream()])
```

### FingersCrossed — Buffer Until Error

```python
from plainlog import configure_log
from plainlog.processors import FingersCrossed, SimpleFormatter, Stream

# Buffer up to 100 records, flush everything on ERROR (level 40)
handler = FingersCrossed(
    Stream(),
    action_level=40,
    buffer_size=100,
)
configure_log(processors=[SimpleFormatter(), handler])
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

### Redacting Sensitive Fields

`redact_fields` matches exact key names; `redact_by_pattern` matches any key
containing a given substring. Both are case-insensitive and recurse through
nested dicts and lists, including dicts inside lists. Matching applies to leaf
values: when a matched key holds a container, the processor descends into it
and masks matching leaves instead of replacing the container. Place them early
in the pipeline, before any formatter, so formatted/serialized output never
contains the raw value. They scrub matching keys anywhere in the record — at
the top level and inside nested containers. Secrets interpolated directly into
the message string (e.g. `log.info(f"password={pw}")`) are not caught.

```python
import sys
from plainlog import configure_log, logger
from plainlog.processors import (
    ConsoleRenderer,
    Stream,
    format_message,
    redact_by_pattern,
)

configure_log(
    processors=[
        redact_by_pattern("password", "token", "secret", "api_key"),
        format_message,
        ConsoleRenderer(colors=False),
        Stream(sys.stdout),
    ]
)

log = logger.new()
log.info("login attempt", username="alice", password="hunter2")
# -> ... username=alice password=***REDACTED***  (field order may vary)
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

### JsonFormatter

::: plainlog.processors.JsonFormatter
