"""Benchmark comparing stdlib logging vs plainlog performance."""

import logging
import os
import timeit
from statistics import mean, stdev

from plainlog import logger
from plainlog._base import Record
from plainlog.configure import apply_log_profile
from plainlog.formatters import JsonFormatter, SimpleFormatter
from plainlog.handlers import ProcessingHandler, StreamHandler
from plainlog.processors import add_caller_info


class NullHandler:
    """Handler that discards records — measures pure overhead."""

    def preprocess(self, record: Record) -> Record:
        return record

    def process(self, record: Record) -> Record:
        return record

    def close(self) -> None:
        pass


DEVNULL = os.devnull

N = 200_000
RUNS = 5

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


def setup_plainlog_empty() -> None:
    apply_log_profile("empty", level="WARNING")


def setup_plainlog_null() -> None:
    logger.configure(level="DEBUG", handler=NullHandler())


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
        "func": plainlog_log_json,
    },
    {
        "name": "plainlog /dev/null (processing with caller)",
        "setup": setup_plainlog_caller,
        "func": plainlog_log_caller,
    },
]


def run() -> None:
    results: list[dict] = []

    for bench in BENCHMARKS:
        times: list[float] = []
        for _ in range(RUNS):
            bench["setup"]()
            t = timeit.timeit(bench["func"], number=N)
            times.append(t / N)
        avg = mean(times)
        sd = stdev(times) if len(times) > 1 else 0.0
        results.append(
            {"name": bench["name"], "avg_ns": avg * 1e9, "stdev_ns": sd * 1e9}
        )

    print(f"{'Scenario':<40} {'avg (ns)':>10} {'stdev (ns)':>10}")
    print("-" * 62)
    for r in results:
        print(f"{r['name']:<40} {r['avg_ns']:>10.1f} {r['stdev_ns']:>10.1f}")


if __name__ == "__main__":
    run()
