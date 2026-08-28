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
| `src/plainlog/_base.py` | Core types: `Record`, `RecordException`, `HandlerProtocol`. (Log level is a plain `int`; `level_name`/`extra`/`exception` live on the record.) |
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
