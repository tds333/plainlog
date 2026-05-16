# Plainlog vs Python Standard Library Logging

| Aspect | plainlog | stdlib `logging` |
|---|---|---|
| **Architecture** | Logger and Core are cleanly separated via a thread-safe `SimpleQueue`. The logger runs in the application thread; the Core runs in a dedicated daemon thread. | Logger, Handler, and Formatter all run in the caller's thread. No built-in queue-based decoupling. |
| **Blocking behavior** | Non-blocking by design. The logger merely builds a dict record and enqueues it; all I/O and formatting happen in the Core's background thread. | Synchronous and blocking in the hot path (I/O inside `emit()` blocks the caller). |
| **Record type** | Log records are plain Python `dict` objects. | Log records are `LogRecord` instances (a class with many attributes). |
| **Logger hierarchy** | No logger hierarchy. Multiple loggers share one singleton Core. Logger names are flat/dotted strings but not hierarchical beyond that. | Strict hierarchical logger tree with parent-child propagation. |
| **Configuration** | Configuration is done solely on the Core (handlers, processors, level). Uses named profiles (e.g. `"default"`, `"develop"`, `"json"`, `"file"`). Environment variables `PLAINLOG_PROFILE` and `PLAINLOG_LEVEL` control initial setup. | Configuration is done on loggers (propagation, level, filters) and handlers separately. Typically requires multiple lines of boilerplate. |
| **Processors / Preprocessors** | A pipeline of callables: **preprocessors** run in the application thread (before enqueueing), **processors** run in the Core thread (after dequeueing). This is a first-class concept. | No direct equivalent. Filters exist but are less composable. |
| **Speed** | Logger hot path is minimal: build a dict, check level, enqueue to queue. Much faster than stdlib on the hot path. | Hot path does level comparison, formatting, filter checks, and handler emission all inline. |
| **Async support** | Same sync interface works in async code because logging is always non-blocking (the queue-based Core handles I/O). | Requires `QueueHandler`/`QueueListener` setup for similar behavior, or dedicated async handlers with different method names. |
| **`bind` / `unbind` / `context`** | Offers `logger.bind(**kwargs)` (returns a new logger with extra fields), `logger.unbind(*args)`, `logger.context(**kwargs)` (context var), and `logger.contextualize(**kwargs)` context manager. | No built-in equivalent; must use `LoggerAdapter` or `extra` dict manually. |
| **Log levels** | Reuses stdlib level numbers and names (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`, `NOTSET`). Does not invent its own. | The original source of these levels. |
| **Profiles** | Ships with 15+ named configuration profiles (default, develop, fingerscrossed, simple, cloud, json, file, fast, empty, no_init, etc.) for one-liner setup. | No profiles concept. |
| **Dependencies** | Zero external dependencies. | Part of the Python standard library. |
| **Setup** | `from plainlog import logger` — ready to use immediately. | `import logging; logging.basicConfig(...); logger = logging.getLogger(...)` — requires boilerplate. |

## Design Philosophy

plainlog is **simple, small, fast, and non-blocking** by default. It borrows best ideas from structlog (processor pipelines, dev console rendering, bind/unbind), loguru (logger/core separation with queue), logbook (FingersCrossedHandler), and Twisted (record-as-dict philosophy).
