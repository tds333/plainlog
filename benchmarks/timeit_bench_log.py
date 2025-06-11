from plainlog import logger, logger_core, configure_log
from time import sleep
from plainlog.processors import (
    add_caller_info,
    filter_by_name,
    FilterList,
)
from plainlog.handlers import WrapStandardHandler, ConsoleHandler, JsonHandler, FileHandler, StreamHandler

# from plainlog._rich_handler import RichHandler
from plainlog.handlers import JsonHandler
from plainlog.warnings import capture_warnings
from plainlog.formatters import SimpleFormatter
import logging
import pprint

import timeit

# capture_warnings(True)

log = logger.new(__name__)
std_log = logging.getLogger(__name__)


def std_create_logger():
    logging.getLogger("mylogger")


def do_log():
    log.info("my info log")
    log.error("my error log")
    log.warning("my warning log")
    log.debug("my debug")


def do_log_stream():
    log.info("my info log")
    log.error("my error log")
    log.warning("my warning log")
    log.debug("my debug")


def std_do_log():
    std_log.info("my info log")
    std_log.error("my error log")
    std_log.warning("my warning log")
    std_log.debug("my debug")


def create_logger():
    logger.new("mylogger")


def setup_log():
    configure_log("empty")
    # logger.get_core().add(lambda x: None, level="DEBUG")


def setup_stream_log():
    configure_log("fast")


def setup_std_log():
    logger = logging.getLogger(__name__)
    logger.addHandler(logging.NullHandler())
    # logger.setLevel("DEBUG")
    # logger.setLevel("CRITICAL")


function_list = [
    (create_logger, setup_log),
    (do_log, setup_log),
    (do_log_stream, setup_stream_log),
    (std_create_logger, setup_std_log),
    (std_do_log, setup_std_log),
]


def bench_functions(functions):
    result = {}
    amount = 100_000
    for func, setup_func in functions:
        name = str(func.__name__)
        execution_time = timeit.timeit(func, number=amount, setup=setup_func)
        average_execution_time = execution_time / amount
        # print(f"Average execution time: {average_execution_time} seconds")
        # print(f"Execution time for {name!r}: {execution_time} seconds")
        result[name] = (execution_time, average_execution_time)

    return result


def main():
    result = bench_functions(function_list)
    sleep(2)
    pprint.pprint(result)


if __name__ == "__main__":
    main()
