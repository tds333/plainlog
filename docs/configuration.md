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

A profile is a named preset that configures the logger's handler, level, and
options in one call. Use `apply_log_profile()` to
activate one:

```python
from plainlog import logger
from plainlog.configure import apply_log_profile

apply_log_profile("develop", level="DEBUG")
logger.info("ready")
```

### Available Profiles

#### Convenience Profiles

| Profile | Handler | Output | Notes |
|---------|---------|--------|-------|
| ``default`` | [`DefaultHandler`](handlers.md#defaulthandler) | stdout | Compact default format |
| ``develop`` | [`DevelopHandler`](handlers.md#develophandler) | stderr | Colorized, caller info, error printing |
| ``simple`` | [`StreamHandler`](handlers.md#streamhandler) | stderr | Minimal format |
| ``console_no_color`` | [`ConsoleHandler`](handlers.md#consolehandler) | stderr | No ANSI codes, error printing |

#### Structured / JSON Output

| Profile | Handler | Output | Notes |
|---------|---------|--------|-------|
| ``cloud`` | [`JsonHandler`](handlers.md#jsonhandler) | stderr | Compact JSON, no indent |
| ``json`` | [`JsonHandler`](handlers.md#jsonhandler) | stderr | Pretty-printed JSON (indent=2) |
| ``fast`` | [`StreamHandler`](handlers.md#streamhandler) | stderr | SimpleFormatter, no extras |

#### File Output

| Profile | Handler | Output | Notes |
|---------|---------|--------|-------|
| ``file`` | [`FileHandler`](handlers.md#filehandler) | ``plainlog.log`` | With rotation watching |
| ``fingerscrossed_file`` | [`FingersCrossedHandler`](handlers.md#fingerscrossedhandler) wrapping FileHandler | ``plainlog.log`` | Buffer until action level |

#### Buffered / Conditional

| Profile | Handler | Notes |
|---------|---------|-------|
| ``fingerscrossed`` | [`FingersCrossedHandler`](handlers.md#fingerscrossedhandler) wrapping ConsoleHandler | stderr, colorized, buffer until ERROR |

Additional kwargs: ``action_level``, ``buffer_size``, ``reset``.

#### Special-Purpose

| Profile | Effect |
|---------|--------|
| ``empty`` | Removes all handlers (silent logging) |
| ``no_init`` | Does nothing — logger stays as-is |
| ``std_handler_default`` | Installs `StdInterceptHandler` on stdlib root, then applies ``default`` |
| ``std_handler_develop`` | Installs StdInterceptHandler on stdlib root, then applies ``develop`` |

---

## Registering Custom Profiles

Use `add_profile()` to register your own:

```python
from plainlog import logger
from plainlog.configure import add_profile, apply_log_profile
from plainlog.handlers import ConsoleHandler

def my_profile(level=None, **kwargs):
    logger.configure(
        handler=ConsoleHandler(colors=False),
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
from plainlog.handlers import FileHandler

logger.configure(
    handler=FileHandler("app.log"),
    level="DEBUG",
    print_errors=True,
)
```

---

## API Reference

### apply_log_profile

::: plainlog.configure.apply_log_profile

### add_profile

::: plainlog.configure.add_profile
