# Base Types

The ``plainlog._base`` module defines the foundational types used
throughout the library.

## Type Aliases

| Alias | Description |
|-------|-------------|
| `Msg` | Log message content — accepts any type. |
| `Record` | A log record — a plain Python ``dict``. |
| `level` | Log level — a plain ``int`` (e.g. ``10``, ``20``, ``30``). The human-readable name is stored as ``level_name`` on each record. |
| `UniversalProcessorProtocol` | Union of `ProcessorProtocol` and `ProcessorCloseProtocol` — a processor with or without a ``close()`` method. |

## API Reference

### RecordException

::: plainlog._base.RecordException

### ProcessorProtocol

::: plainlog._base.ProcessorProtocol

### ProcessorCloseProtocol

::: plainlog._base.ProcessorCloseProtocol

### UniversalProcessorProtocol

::: plainlog._base.UniversalProcessorProtocol
