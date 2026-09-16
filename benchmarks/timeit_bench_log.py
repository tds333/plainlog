"""Benchmark plainlog against stdlib logging with timeit.

Scenarios are paired so each plainlog row has a stdlib counterpart doing the
same amount of work. Nothing is written to the terminal: the "no output" row
discards records, and the "/dev/null" row writes to ``os.devnull``.
"""

import logging
import os
import timeit
from statistics import mean
from typing import Callable

from plainlog import apply_log_profile, logger
from plainlog._logger import logger_core

NUMBER = 100_000
RUNS = 3

DEVNULL = open(os.devnull, "w")

bench_std = logging.getLogger("bench.stdlib")


def plainlog_create_logger() -> None:
    logger.new("bench.mylogger")


def stdlib_create_logger() -> None:
    logging.getLogger("bench.mylogger")


def plainlog_log() -> None:
    logger.info("my info log")
    logger.error("my error log")
    logger.warning("my warning log")
    logger.debug("my debug")


def stdlib_log() -> None:
    bench_std.info("my info log")
    bench_std.error("my error log")
    bench_std.warning("my warning log")
    bench_std.debug("my debug")


def setup_plainlog_empty() -> None:
    apply_log_profile("empty", level="DEBUG")


def setup_plainlog_devnull() -> None:
    apply_log_profile("fast", level="DEBUG", stream=DEVNULL)


def setup_stdlib_null() -> None:
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(logging.NullHandler())
    root.setLevel(logging.DEBUG)
    bench_std.setLevel(logging.DEBUG)


def setup_stdlib_devnull() -> None:
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(logging.StreamHandler(DEVNULL))
    root.setLevel(logging.DEBUG)
    bench_std.setLevel(logging.DEBUG)


SCENARIOS: list[tuple[str, Callable, Callable, Callable, Callable]] = [
    (
        "create logger",
        plainlog_create_logger,
        lambda: None,
        stdlib_create_logger,
        lambda: None,
    ),
    (
        "log (no output)",
        plainlog_log,
        setup_plainlog_empty,
        stdlib_log,
        setup_stdlib_null,
    ),
    (
        "log -> /dev/null",
        plainlog_log,
        setup_plainlog_devnull,
        stdlib_log,
        setup_stdlib_devnull,
    ),
]


def bench(func: Callable, setup: Callable, number: int, runs: int) -> float:
    times = []
    for _ in range(runs):
        setup()
        times.append(timeit.timeit(func, number=number) / number)
    logger_core.wait_for_processed()
    return mean(times) * 1e9


def main() -> None:
    print(f"plainlog vs stdlib logging (timeit, {NUMBER} iterations x {RUNS} runs)")
    print()
    header = f"{'scenario':<20} {'plainlog':>12} {'stdlib':>12} {'ratio':>8}"
    print(header)
    print("-" * len(header))

    for label, pl_func, pl_setup, std_func, std_setup in SCENARIOS:
        pl_ns = bench(pl_func, pl_setup, NUMBER, RUNS)
        std_ns = bench(std_func, std_setup, NUMBER, RUNS)
        ratio = std_ns / pl_ns if pl_ns else 0.0
        print(f"{label:<20} {pl_ns:>9.1f} ns {std_ns:>9.1f} ns {ratio:>7.2f}x")

    print()
    print("ratio > 1.0 means plainlog is faster than stdlib.")


if __name__ == "__main__":
    main()
