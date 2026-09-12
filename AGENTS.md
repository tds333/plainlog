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
- Processor/formatter/handler tests are consolidated in `tests/test_processors.py`.
- avoid test classes use functions instead, classes only if to test methods of a class

## Docs

- Built with Zensical + mkdocstrings.
- Navigation defined explicitly in `zensical.toml` `[nav]`.
- API pages use `::: module.path` directives with explicit `### Heading` above each.
- Doc pages: `docs/index.md`, `docs/logger.md`, `docs/configuration.md`, `docs/processors.md`, `docs/base.md`, `docs/comparison_to_stdlib.md`, `docs/changelog.md`.

## Architecture

- **Logger** — lightweight, builds a `Record` dict, enqueues to Core. Lives in app thread.
- **Core** — background thread, dequeues records, runs configured processors. Singleton per process.
- **Processor** — implements `ProcessorProtocol` (optionally `ProcessorCloseProtocol`).
  - Runs in the core thread; an optional `close()` handles cleanup.
  - Return `{}` to drop a record.
- **Formatter** — a processor that sets the formatted string in `record["message"]` and returns the record.
- **Handler** — a processor that performs output by writing `record["message"]` (e.g. `Stream`, `FileWriter`, `AsyncBridge`).
- **Composition** — `logger.configure(processors=[...])` sets an ordered processor list run in the Core thread; the usual pattern is a formatter followed by a handler (e.g. `[JsonFormatter(), Stream()]`). `SubProcessor` runs a nested pipeline on a record copy. `processors=()` clears the list, `None` leaves it unchanged.
- **Record** — plain `Dict[str, Any]`.
- **Profiles** — named presets in `configure.py` `_profiles` dict. Used via `apply_log_profile("name")`.
- **Env config** — `PLAINLOG_PROFILE` and `PLAINLOG_LEVEL` read at import time.

## Key files

| File | Role |
|------|------|
| `src/plainlog/__init__.py` | Public API surface, auto-configures on import |
| `src/plainlog/_logger.py` | Logger + Core classes |
| `src/plainlog/configure.py` | `apply_log_profile()`, `add_profile()`, profile registry |
| `src/plainlog/processors.py` | Processors, formatters and handlers (single module) |
| `src/plainlog/_dev.py` | `ConsoleRenderer` (processor that renders dev output into `record["message"]`) |
| `src/plainlog/std.py` | Stdlib logging bridge |
| `src/plainlog/_base.py` | Core types: `Record`, `RecordException`, `ProcessorProtocol`, `ProcessorCloseProtocol`. (Log level is a plain `int`; `level_name`/`extra`/`exception` live on the record.) |
| `zensical.toml` | Doc build config + mkdocstrings options |

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
