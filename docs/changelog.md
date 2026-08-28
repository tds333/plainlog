# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.4.0]: https://github.com/tds333/plainlog/compare/0.3.0...0.4.0
[0.3.0]: https://github.com/tds333/plainlog/compare/0.2.0...0.3.0
