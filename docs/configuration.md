# Configuration

plainlog can be configured via profiles, environment variables, or direct
API calls.

---

## Auto-Configuration on Import

When you ``from plainlog import logger``, the library reads two environment
variables and applies the selected profile automatically:

| Variable | Default | Description |
|----------|---------|-------------|
| ``PLAINLOG_PROFILE`` | ``"default"`` | Profile name to apply at import |
| ``PLAINLOG_LEVEL`` | ``"NOTSET"`` | Minimum log level override |

```python
# PLAINLOG_PROFILE=develop PLAINLOG_LEVEL=DEBUG python app.py
from plainlog import logger  # auto-configures "develop" at DEBUG
```

---

## Profiles

A profile is a named preset that configures the logger's processors, level,
and options in one call. Use `apply_log_profile()` to
activate one:

```python
from plainlog import logger
from plainlog.configure import apply_log_profile

apply_log_profile("develop", level="DEBUG")
logger.info("ready")
```

### Available Profiles

#### Convenience Profiles

| Profile | Processors | Output | Notes |
|---------|------------|--------|-------|
| ``default`` | [`SimpleFormatter`](processors.md#simpleformatter) + [`Stream`](processors.md#stream) | stdout | Default single-line format |
| ``develop`` | `format_message` + `ConsoleRenderer` + [`Stream`](processors.md#stream) + `print_processor_error` | stderr | Colorized, caller info (verbose), error printing |
| ``develop_no_color`` | `format_message` + `ConsoleRenderer` + [`Stream`](processors.md#stream) + `print_processor_error` | stderr | No ANSI codes, caller info (verbose), error printing |

#### Structured / JSON Output

| Profile | Processors | Output | Notes |
|---------|------------|--------|-------|
| ``cloud`` | [`JsonFormatter`](processors.md#jsonformatter) + [`Stream`](processors.md#stream) | stderr | Compact JSON, no indent |
| ``json`` | [`JsonFormatter`](processors.md#jsonformatter) + [`Stream`](processors.md#stream) | stderr | Pretty-printed JSON (indent=2) |

#### File Output

| Profile | Processors | Output | Notes |
|---------|------------|--------|-------|
| ``file`` | [`SimpleFormatter`](processors.md#simpleformatter) + [`FileWriter`](processors.md#filewriter) | ``plainlog.log`` | With rotation watching |
| ``fingerscrossed_file`` | [`SimpleFormatter`](processors.md#simpleformatter) + [`FingersCrossed`](processors.md#fingerscrossed) wrapping [`FileWriter`](processors.md#filewriter) | ``plainlog.log`` | Buffer until action level |

#### Buffered / Conditional

| Profile | Processors | Notes |
|---------|------------|-------|
| ``fingerscrossed`` | `format_message` + `ConsoleRenderer` + [`FingersCrossed`](processors.md#fingerscrossed) wrapping [`Stream`](processors.md#stream) + `print_processor_error` | stderr, colorized, buffer until ERROR |

Additional kwargs:

- ``stream`` — output stream for ``default``, ``develop``, ``develop_no_color``, ``cloud``, ``json``.
- ``format`` — format string for ``default``, ``file``, ``fingerscrossed_file``.
- ``action_level``, ``buffer_size``, ``reset`` — buffering options for ``fingerscrossed`` and ``fingerscrossed_file``.

#### Special-Purpose

| Profile | Effect |
|---------|--------|
| ``empty`` | Removes all processors (silent logging) |
| ``no_init`` | Does nothing — logger stays as-is |
| ``std_handler_default`` | Installs `StdInterceptHandler` on stdlib root, then applies ``default`` |
| ``std_handler_develop`` | Installs StdInterceptHandler on stdlib root, then applies ``develop`` |

---

## Registering Custom Profiles

Use `add_profile()` to register your own:

```python
from plainlog import logger
from plainlog.configure import add_profile, apply_log_profile
from plainlog.processors import SimpleFormatter, Stream

def my_profile(level=None, **kwargs):
    logger.configure(
        processors=[SimpleFormatter(), Stream()],
        level=level,
    )

add_profile("my_custom", my_profile)
apply_log_profile("my_custom", level="INFO")
```

Returns ``True`` if added, ``False`` if the name already exists.

---

## Direct Configuration

Instead of profiles, call `configure()` directly:

```python
from plainlog import logger
from plainlog.processors import FileWriter

logger.configure(
    processors=[FileWriter("app.log")],
    level="DEBUG",
)
```

---

## API Reference

### apply_log_profile

::: plainlog.configure.apply_log_profile

### add_profile

::: plainlog.configure.add_profile
