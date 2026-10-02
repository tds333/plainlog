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

A profile is a named preset that returns a processor pipeline. Use
`configure_log(profile=...)` to apply one, passing `level=` to set the minimum
level at the same time:

```python
from plainlog import configure_log, logger

configure_log(profile="develop", level="DEBUG")
log = logger.new()
log.info("ready")
```

### Available Profiles

#### Convenience Profiles

| Profile | Processors | Output | Notes |
|---------|------------|--------|-------|
| ``default`` | [`SimpleFormatter`](processors.md#simpleformatter) + [`Stream`](processors.md#stream) | stdout | Default single-line format |
| ``develop`` | `format_message` + `ConsoleRenderer` + [`Stream`](processors.md#stream) + `print_processor_error` | stderr | Colorized, error printing |
| ``develop_no_color`` | `format_message` + `ConsoleRenderer` + [`Stream`](processors.md#stream) + `print_processor_error` | stderr | No ANSI codes, error printing |

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

Use `add_profile()` to register your own. A profile is a callable that takes
keyword arguments and returns a processor list, or `None` to leave the
pipeline unchanged:

```python
from plainlog.configure import add_profile, configure_log
from plainlog.processors import SimpleFormatter, Stream

def my_profile(**kwargs):
    return [SimpleFormatter(), Stream()]

add_profile("my_custom", my_profile)
configure_log(profile="my_custom", level="INFO")
```

Returns ``True`` if added, ``False`` if the name already exists.

---

## Direct Configuration

Instead of profiles, call `configure_log()` directly:

```python
from plainlog import configure_log
from plainlog.processors import FileWriter

configure_log(
    processors=[FileWriter("app.log")],
    level="DEBUG",
)
```

---

## Processor Lifecycle and Shutdown

`configure()` only swaps the processor list — it does not close the processors
it replaces. Replacing a processor therefore leaves its resources (open files,
async bridges) open until you release them explicitly.

`Core` tracks every processor that exposes a `close()` method. `Core.close()`
releases those resources and detaches the pipeline while leaving the worker
thread running; `Core.shutdown()` also stops the worker and is what runs at
interpreter exit.

```python
from plainlog._logger import Core

core = Core()
core.configure(processors=[], level="DEBUG")

core.close()      # release registered resources; the worker keeps running
core.shutdown()   # release resources and stop the worker
```

Switching configuration does not release the previous processors unless you
ask: pass `close_before_configure=True` to `configure_log()` to close the
currently registered processors before installing the new pipeline. A profile
that returns `None` (such as `no_init`) leaves the pipeline untouched.

---

## API Reference

### configure_log

::: plainlog.configure.configure_log

### add_profile

::: plainlog.configure.add_profile
