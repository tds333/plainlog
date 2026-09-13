# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0] - 2026-09-13

### Changed

- **Everything is a processor.** `configure(handler=...)` is replaced by
  `configure(processors=[...])`. The Core runs an ordered processor list; pass
  `[]`/`()` to clear it and `None` to leave it unchanged. The usual pipeline is
  a formatter followed by a handler (e.g. `[JsonFormatter(), Stream()]`).
- **Formatters are processors.** `SimpleFormatter`, `DefaultFormatter`,
  `JsonFormatter` and `ConsoleRenderer` now set `record["message"]` and return
  the record instead of returning a string.
- **Merged `formatters.py` and `handlers.py` into `plainlog.processors`.** The
  `plainlog.formatters` and `plainlog.handlers` modules are gone.
- **Handler renames.** `StreamHandler` → `Stream`, `FileHandler` → `FileWriter`,
  `AsyncHandler` → `AsyncBridge`, `FingersCrossedHandler` → `FingersCrossed`.
- **`JsonHandler`, `ConsoleHandler` and `DefaultHandler` removed.** Build the
  equivalent pipeline from a formatter plus `Stream`.
- Tests consolidated into `tests/test_processors.py`.
- Documentation reorganized; `docs/handlers.md` is now `docs/processors.md`.

### Added

- `SubProcessor` — runs a nested processor pipeline on a copy of the record.
- `allow_by_name` processor.
- `ProcessorProtocol`, `ProcessorCloseProtocol` and `UniversalProcessorProtocol`
  in `plainlog._base`.
- Fork support: the Core worker is restarted in forked child processes.

### Removed

- `BaseHandler`, `ProcessingHandler` and the preprocessor concept.
- `preformat_message`.

### Fixed

- Thread-safety of concurrent logging and reconfiguration.
- Async handler (`AsyncBridge`) reliability.

## [0.4.0] - 2026-08-28

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

## [0.3.0]

### Changed

- Renamed internal entry points; the main interface now lives on `logger`
  (`logger.debug`, `logger.log`, `logger.configure`, ...). The `Core` is no
  longer part of the public surface.

### Added

- Initial documentation site and runnable doc examples (`pytest-examples`).
- More tests and benchmark coverage.

[Unreleased]: https://github.com/tds333/plainlog/compare/0.4.0...HEAD
[0.4.0]: https://github.com/tds333/plainlog/compare/0.3.0...0.4.0
[0.3.0]: https://github.com/tds333/plainlog/compare/0.2.0...0.3.0
