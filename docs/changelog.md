# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Changed

- **Record schema flattened: the `extra` key is gone.** Keyword arguments
  passed to `logger.info(...)`, `bind()` and `contextualize()` now become
  top-level fields on the record instead of being nested under
  `record["extra"]`.
- `SimpleFormatter` and `JsonFormatter` write the rendered string to
  `record["formatted_message"]` instead of overwriting `record["message"]`.
- `JsonFormatter` serializes a fixed set of keys plus `additional_keys`;
  arbitrary user fields are no longer included automatically.
- `SubProcessor` runs its nested processors on a shallow `copy` of the
  record (previously `deepcopy`).
- `Logger.error()`, `critical()` and `exception()` request caller info
  (`function`, `line`, ...) by default.
- Documentation and benchmark examples now create a child logger with
  `logger.new()` and log through it rather than logging to the root
  `logger`. The benchmark also logs through a bound name so CPython's
  imported-name call-site overhead does not skew the comparison.

### Removed

- `eval_extra`, `eval_lambda_extra` and `remove_extra_items` processors —
  fields are plain top-level record keys now.
- The `extra` parameter of `Logger(...)` and the `verbose` parameter of
  `Logger(...)`, `Logger.new()` and `Logger.configure()`; pass keyword
  arguments directly and use `caller_info=True` for caller info.

## 0.7.0 - 2026-09-20

### Added

- `develop_no_color` profile — like `develop` but without ANSI colors.

### Changed

- `Logger.new()` inherits the parent logger's `verbose` setting when
  `verbose` is not given, instead of always defaulting to `False`.
- `SimpleFormatter` now renders a full ISO timestamp and appends `extra`
  instead of dropping it.
- The `default` profile now uses `SimpleFormatter` (writing to stdout).
- `develop` honors a `stream` kwarg; `default`, `file` and
  `fingerscrossed_file` accept a `format` kwarg.
- Profiles now set `verbose` explicitly, so applying a profile no longer
  inherits a previous `verbose` setting. `Logger.configure(verbose=None)` and
  `Logger.new(verbose=None)` keep inheriting, as before.

### Removed

- `DefaultFormatter` — use `SimpleFormatter` instead.
- Profiles `simple`, `fast` and `console_no_color` (`console_no_color` is
  replaced by `develop_no_color`).

### Fixed

- `std_handler_default` and `std_handler_develop` now forward their kwargs
  (e.g. `stream`, `format`) to the wrapped profile.
- Documentation corrections: profile count, changelog comparison links, and
  the missing callable `logger(...)` form plus manual `context()` /
  `reset_context()` usage.
- Corrected `Logger` docstrings: removed the non-existent `core` attribute
  and refreshed the `configure()`, `new()` and `__call__()` descriptions.


## 0.6.0 - 2026-09-18

### Added

- `redact_fields` and `redact_by_pattern` processors — mask sensitive `extra` values by exact key name or substring pattern.
  contributed by @kashyapm94

### Changed

- License changed from Apache-2.0 OR MIT to BSD 3-Clause.


## 0.5.0 - 2026-09-13

### Changed

- **Everything is a processor.** `configure(handler=...)` is replaced by
  `configure(processors=[...])`. The Core runs an ordered processor list.
  The usual pipeline is filter, format, handle.
- **Formatters are processors.** `SimpleFormatter`, `DefaultFormatter`,
  `JsonFormatter` and `ConsoleRenderer` now set `record["message"]` and return
  the record instead of returning a string.
- **Merged `formatters.py` and `handlers.py` into `plainlog.processors`.** The
  `plainlog.formatters` and `plainlog.handlers` modules are gone.
- **Handler renames.** `StreamHandler` → `Stream`, `FileHandler` → `FileWriter`,
  `AsyncHandler` → `AsyncBridge`, `FingersCrossedHandler` → `FingersCrossed`.
- **`JsonHandler`, `ConsoleHandler` and `DefaultHandler` removed.** Build the
  equivalent pipeline from a formatter plus `Stream`.
- **`configure(print_errors=...)` removed.** Processor errors are now emitted by
  the new `print_processor_error` processor instead of a Core flag.
- Tests consolidated into `tests/test_processors.py`.
- Documentation reorganized; `docs/handlers.md` is now `docs/processors.md`.

### Added

- `SubProcessor` — runs a nested processor pipeline on a copy of the record.
- `print_processor_error` — prints a record's processor error to stderr.
- `ProcessorProtocol`, `ProcessorCloseProtocol` and `UniversalProcessorProtocol`
  in `plainlog._base`.
- Fork support: the Core worker is restarted in forked child processes.
- `verbose=True` to Logger, adding caller info (`function`, `line`, ...) to the record.


### Removed

- `BaseHandler`, `ProcessingHandler` and the preprocessor concept.
- `preformat_message`.

### Fixed

- Thread-safety of concurrent logging and reconfiguration.
- Async handler (`AsyncBridge`) reliability.

## 0.4.0 - 2026-08-28

### Changed

- **Log level is now a plain `int`.** The `Level` `NamedTuple` was removed.
  `record["level"]` is an `int` (e.g. `10`, `20`, `30`), and the human-readable
  name is stored alongside it as `record["level_name"]` (a `str`).
- **Record schema simplified.** The separate `context` and `kwargs` keys are now
  merged into the record's `extra` dict. Caller/context variables and per-call
  keyword arguments are all available under `record["extra"]`.
- **Exception handling.** `exc_info` is replaced by `exception`, a
  `RecordException` (pickle-safe) stored under `record["exception"]`.

### Added

- `level_name` (the human-readable level name) is written directly onto every
  record alongside `level`.
- Performance improvements on the logging hot path: `time()` is used instead of
  `datetime` for the record timestamp, and benchmarks against stdlib logging were
  improved.

### Removed

- `Core.level()` method. Level validation is handled internally by
  `_validate_level` (which now uses `logging._checkLevel`).

### Fixed

- Bug with caller-level resolution in `DevelopHandler`.
- Documentation references and examples updated to the new record schema.

## 0.3.0

### Changed

- Renamed internal entry points; the main interface now lives on `logger`
  (`logger.debug`, `logger.log`, `logger.configure`, ...). The `Core` is no
  longer part of the public surface.

### Added

- Initial documentation site and runnable doc examples (`pytest-examples`).
- More tests and benchmark coverage.
