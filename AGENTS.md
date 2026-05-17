# AGENTS.md — plainlog

## Project

Minimal, non-blocking, zero-dependency Python logging library.  
Public API: `from plainlog import logger`. Entrypoint: `src/plainlog/__init__.py`.

## Commands

| Command | What |
|---------|------|
| `make test` | Run tests (current Python) |
| `make cov` | Tests + coverage report |
| `make tests` | Run across all supported Python versions (3.10–3.15, incl. free-threaded) |
| `make lint` | `uvx ruff check src/` |
| `make format` | `uvx ruff format src/` |
| `make type-check` | `uvx ty check src/` |
| `make docs` | Build docs with zensical (`--group docs`) |
| `make build` | `uv build` |

Single test: `uv run pytest tests/test_foo.py::test_bar -x -v`.  
There is no required command ordering — lint/type-check/test are independent.

## Style & Tooling

- Ruff for lint+format, line-length 88.
- Google-style docstrings (enforced by mkdocstrings config).
- `__init__` `Args:` belong in the **class** docstring, not on `__init__`.
- Type hints required.

## Testing

- `pythonpath = ["src"]`, `testpaths = ["tests"]` in pyproject.toml.
- No external test dependencies beyond pytest plugins.
- Code blocks in `README.md` and `docs/*.md` are tested via `pytest-examples`
  (`tests/test_examples.py`). Keep them runnable standalone (full imports).
- Coverage: `make cov` — 97% average.
- avoid test classes use functions instead, classes only if to test methods of a class

## Docs

- Built with Zensical + mkdocstrings.
- Navigation defined explicitly in `zensical.toml` `[nav]`.
- API pages use `::: module.path` directives with explicit `### Heading` above each.
- Doc pages: `docs/logger.md`, `docs/handlers.md`, `docs/base.md`, `docs/comparison_to_stdlib.md`, `docs/index.md`.

## Architecture

- **Logger** — lightweight, builds a `Record` dict, enqueues to Core. Lives in app thread.
- **Core** — background thread, dequeues records, sends to handler. Singleton per process.
- **Handler** — implements `HandlerProtocol` (preprocess → process → close).
  - preprocess runs in app thread; process runs in core thread.
  - Return `{}` to drop a record at any stage.
- **Record** — plain `Dict[str, Any]`.
- **Profiles** — named presets in `configure.py` `_profiles` dict. Used via `apply_log_profile("name")`.
- **Env config** — `PLAINLOG_PROFILE` and `PLAINLOG_LEVEL` read at import time.

## Key files

| File | Role |
|------|------|
| `src/plainlog/__init__.py` | Public API surface, auto-configures on import |
| `src/plainlog/_logger.py` | Logger + Core classes |
| `src/plainlog/configure.py` | `apply_log_profile()`, `add_profile()`, profile registry |
| `src/plainlog/handlers.py` | All built-in handler classes |
| `src/plainlog/processors.py` | Preprocessors and processors |
| `src/plainlog/formatters.py` | Simple, Default, JSON formatters |
| `src/plainlog/std.py` | Stdlib logging bridge |
| `src/plainlog/_base.py` | Core types: `Level`, `Record`, `RecordException`, `HandlerProtocol` |
| `zensical.toml` | Doc build config + mkdocstrings options |
