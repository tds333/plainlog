"""Benchmark comparing stdlib logging vs plainlog performance.

Results are shown side by side with matching scenarios paired together.
"""

import argparse
import json
import logging
import os
import timeit
from datetime import datetime
from statistics import mean

from plainlog import logger
from plainlog._base import Record
from plainlog._logger import logger_core
from plainlog.configure import _profiles, apply_log_profile
from plainlog.formatters import JsonFormatter, SimpleFormatter
from plainlog.handlers import ProcessingHandler, StreamHandler
from plainlog.processors import add_caller_info


class NullHandler:
    """Handler that discards records — measures pure overhead."""

    def preprocess(self, record: Record) -> Record:
        return {}

    def process(self, record: Record) -> Record:
        return record

    def close(self) -> None:
        pass


DEVNULL = os.devnull

N = 200_000
RUNS = 3  # overridden by --iterations / --runs CLI flags

std_log = logging.getLogger(__name__)


def setup_stdlib_null() -> None:
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers.clear()
    root.addHandler(logging.NullHandler())
    std_log.setLevel(logging.DEBUG)


def stdlib_log_noop() -> None:
    std_log.debug("benchmark message 42")


def setup_stdlib_devnull() -> None:
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers.clear()
    root.addHandler(logging.StreamHandler(open(DEVNULL, "w")))
    std_log.setLevel(logging.DEBUG)


def stdlib_log_devnull() -> None:
    std_log.info("benchmark message 42")


def setup_stdlib_dropped() -> None:
    root = logging.getLogger()
    root.setLevel(logging.WARNING)
    root.handlers.clear()
    root.addHandler(logging.NullHandler())
    std_log.setLevel(logging.WARNING)


def stdlib_log_dropped() -> None:
    std_log.debug("benchmark message 42")


class StdlibJsonFormatter(logging.Formatter):
    """JSON formatter for stdlib — mirrors plainlog's JsonFormatter output."""

    def format(self, record: logging.LogRecord) -> str:
        dt = datetime.fromtimestamp(record.created)

        serializable = {
            "message": record.getMessage(),
            "name": record.name,
            "datetime": dt.isoformat(),
            "timestamp": dt.timestamp(),
            "level_name": record.levelname,
            "level_no": record.levelno,
            "extra": {},
            "process_id": record.process,
            "process_name": record.processName,
        }

        if record.exc_info and record.exc_info[0] is not None:
            exc_type, exc_value, _ = record.exc_info
            serializable["exception"] = {
                "type": exc_type.__name__,
                "value": exc_value,
                "traceback": record.exc_text is not None,
            }

        return json.dumps(serializable, default=str, ensure_ascii=False)


def setup_stdlib_json() -> None:
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers.clear()
    handler = logging.StreamHandler(open(DEVNULL, "w"))
    handler.setFormatter(StdlibJsonFormatter())
    root.addHandler(handler)
    std_log.setLevel(logging.DEBUG)


def stdlib_log_json() -> None:
    std_log.info("benchmark message 42")


def setup_plainlog_empty() -> None:
    apply_log_profile("empty", level="WARNING")


def setup_plainlog_null() -> None:
    logger.configure(level="WARNING", handler=NullHandler())


def setup_plainlog_simple() -> None:
    logger.configure(
        level="DEBUG",
        handler=StreamHandler(open(DEVNULL, "w"), SimpleFormatter("{message}")),
    )


def setup_plainlog_json() -> None:
    logger.configure(
        level="DEBUG",
        handler=StreamHandler(open(DEVNULL, "w"), JsonFormatter()),
    )


def setup_plainlog_caller() -> None:
    logger.configure(
        level="DEBUG",
        handler=ProcessingHandler(
            preprocessors=[add_caller_info],
            handler=StreamHandler(open(DEVNULL, "w"), SimpleFormatter("{message}")),
        ),
    )


def plainlog_log() -> None:
    logger.debug("benchmark message 42")


def setup_plainlog_develop() -> None:
    from plainlog.handlers import DevelopHandler

    logger.configure(
        level="DEBUG",
        handler=DevelopHandler(open(DEVNULL, "w"), colors=False),
        print_errors=True,
    )


def plainlog_log_develop() -> None:
    logger.info("benchmark message 42")


def plainlog_log_json() -> None:
    logger.info("benchmark message 42")


def plainlog_log_caller() -> None:
    logger.warning("benchmark message 42")


BENCHMARKS: list[dict] = [
    {"name": "stdlib NullHandler", "setup": setup_stdlib_null, "func": stdlib_log_noop},
    {
        "name": "stdlib /dev/null (StreamHandler)",
        "setup": setup_stdlib_devnull,
        "func": stdlib_log_devnull,
    },
    {
        "name": "stdlib dropped (level filter)",
        "setup": setup_stdlib_dropped,
        "func": stdlib_log_dropped,
    },
    {
        "name": "stdlib /dev/null (json)",
        "setup": setup_stdlib_json,
        "func": stdlib_log_json,
    },
    {
        "name": "plainlog empty (dropped)",
        "setup": setup_plainlog_empty,
        "func": plainlog_log,
    },
    {
        "name": "plainlog NullHandler",
        "setup": setup_plainlog_null,
        "func": plainlog_log,
    },
    {
        "name": "plainlog /dev/null (simple)",
        "setup": setup_plainlog_simple,
        "func": plainlog_log,
    },
    {
        "name": "plainlog /dev/null (json)",
        "setup": setup_plainlog_json,
        "func": plainlog_log,
    },
    {
        "name": "plainlog /dev/null (caller)",
        "setup": setup_plainlog_caller,
        "func": plainlog_log,
    },
]


DEVNULL_FD = open(DEVNULL, "w")


def _make_profile_bench(name: str) -> dict:
    def setup():
        apply_log_profile(name, level="DEBUG")
        # redirect handler output to devnull after profile applies its handler
        h = logger_core._handler
        if h is not None:
            _silence_handler(h)

    return {"name": f"profile {name}", "setup": setup, "func": plainlog_log}


def _silence_handler(h: object) -> None:
    if hasattr(h, "_stream"):
        h._stream = DEVNULL_FD  # type: ignore[assignment]
    if hasattr(h, "_handler") and h._handler is not None:
        _silence_handler(h._handler)


BENCHMARKS.extend(_make_profile_bench(p) for p in _profiles)


def run() -> None:
    results: dict[str, float] = {}

    for bench in BENCHMARKS:
        times: list[float] = []
        for _ in range(RUNS):
            bench["setup"]()
            t = timeit.timeit(bench["func"], number=N)
            times.append(t / N)
        logger_core.wait_for_processed()
        results[bench["name"]] = mean(times) * 1e9

    pairs = [
        (
            "dropped (level filter)",
            "stdlib dropped (level filter)",
            "plainlog empty (dropped)",
        ),
        ("NullHandler", "stdlib NullHandler", "plainlog NullHandler"),
        (
            "StreamHandler /dev/null",
            "stdlib /dev/null (StreamHandler)",
            "plainlog /dev/null (simple)",
        ),
        (
            "JSON /dev/null",
            "stdlib /dev/null (json)",
            "plainlog /dev/null (json)",
        ),
    ]

    print(f"{'Scenario':<30} {'stdlib (ns)':>12} {'plainlog (ns)':>14} {'ratio':>8}")
    print("-" * 66)
    for label, std_key, pl_key in pairs:
        s = results[std_key]
        p = results[pl_key]
        ratio = s / p if p else 0
        print(f"{label:<30} {s:>12.1f} {p:>14.1f} {ratio:>7.1f}x")

    print()
    print("Plainlog-only scenarios (all profiles):")
    for name in sorted(results):
        if name.startswith("profile "):
            pname = name.removeprefix("profile ")
            print(f"  {pname:<29} {results[name]:>10.1f} ns")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark plainlog vs stdlib logging")
    parser.add_argument("--iterations", type=int, default=N, help="Iterations per run")
    parser.add_argument("--runs", type=int, default=RUNS, help="Number of runs per scenario")
    args = parser.parse_args()
    N, RUNS = args.iterations, args.runs
    run()
