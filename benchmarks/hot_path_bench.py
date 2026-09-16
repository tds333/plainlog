"""Benchmark the plainlog producer hot path (up to the queue put).

Measures the cost of ``Logger._log`` on the calling thread: record
construction and enqueuing to the Core queue. Run it before and after a change
to ``Logger._log`` to quantify the impact.

Uses the public API only. A processor is configured so records actually reach
the queue — with no processors configured ``Logger._log`` returns early.
"""

import argparse
import os
import timeit
from statistics import median

from plainlog import logger
from plainlog._logger import logger_core

DEVNULL = open(os.devnull, "w")


class NullSink:
    """Processor that discards a record after it was built."""

    def __call__(self, record):
        return record

    def close(self):
        pass


def setup_null() -> None:
    logger.configure(level="DEBUG", processors=[NullSink()])


def setup_devnull() -> None:
    from plainlog.processors import SimpleFormatter, Stream

    logger.configure(
        level="DEBUG",
        processors=[SimpleFormatter("{message}"), Stream(DEVNULL)],
    )


def log_one() -> None:
    logger.info("benchmark message 42")


def log_four() -> None:
    logger.info("my info log")
    logger.error("my error log")
    logger.warning("my warning log")
    logger.debug("my debug")


def log_kwargs() -> None:
    logger.info("benchmark message 42", user="alice", count=3)


def measure(func, number: int, runs: int) -> tuple[float, float]:
    times = []
    for _ in range(runs):
        times.append(timeit.timeit(func, number=number) / number)
    logger_core.wait_for_processed()

    return min(times) * 1e9, median(times) * 1e9


def run(number: int, runs: int) -> None:
    print(f"plainlog producer hot path ({number} iterations x {runs} runs)")
    print()
    header = f"{'scenario':<28} {'min ns':>10} {'median ns':>11}"
    print(header)
    print("-" * len(header))

    setup_null()
    for label, func in [
        ("1 log (null sink)", log_one),
        ("4 logs (null sink)", log_four),
        ("1 log + kwargs", log_kwargs),
    ]:
        mn, md = measure(func, number, runs)
        print(f"{label:<28} {mn:>10.1f} {md:>11.1f}")

    setup_devnull()
    mn, md = measure(log_one, number, runs)
    print(f"{'1 log (formatter + devnull)':<28} {mn:>10.1f} {md:>11.1f}")

    setup_null()
    token = logger.context(request_id="bench")
    try:
        mn, md = measure(log_one, number, runs)
    finally:
        logger.reset_context(token)
    print(f"{'1 log + context':<28} {mn:>10.1f} {md:>11.1f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark the producer hot path")
    parser.add_argument("--number", type=int, default=200_000, help="Iterations")
    parser.add_argument("--runs", type=int, default=9, help="Repeats")
    args = parser.parse_args()
    run(args.number, args.runs)
