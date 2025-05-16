import asyncio
import sys
from time import sleep, time

from plainlog import logger, logger_core
from plainlog.formatters import SimpleFormatter

#from plainlog._rich_handler import RichHandler
from plainlog.handlers import (
    AsyncHandler,
    ConsoleHandler,
    FileHandler,
    JsonHandler,
    StreamHandler,
    WrapStandardHandler,
)
from plainlog.processors import (
    DEFAULT_PREPROCESSORS,
    DEFAULT_PROCESSORS,
    FilterList,
    add_caller_info,
    filter_by_name,
)
from plainlog.warnings import capture_warnings


class MyAsyncHandler(AsyncHandler):

    async def write(self, message):
        print("async: ", message)


def timer():
    return time()

def syncf():
    logger.info("start syncf")
    sleep(1)
    logger.info("end syncf")


async def asyncf():
    logger.info("start asyncf")
    await asyncio.sleep(1)
    logger.info("end asyncf")


class LoggerClass:

    #clog = logger.new(name=__qualname__)
    clog = logger.new()

    def __init__(self):
        self.log = logger.new(name=self.__class__.__name__)
        self.nlog = logger.new()

    @logger.contextualize(who="in method 'do_context' of LoggerClass")
    def do_context(self):
        self.log.info("start do_context")
        self.log.info("end do_context")

    def do(self):
        self.log.info("in do")
        self.clog.info("class in do")
        # self.log.name(self.__class__.do.__qualname__).info("in do with name logger")
        self.log.new().info("in do with name logger")




async def main():
    logger_core.add(MyAsyncHandler())
    log = logger.new()
    log.debug("hello")

    log = log.bind(bla=5)
    log.context(special_context="my context")
    log.info("mit extra")

    try:
        1 / 0
    except ZeroDivisionError:
        log.exception("Error")

    xala = lambda: "mystring"

    log.debug("my time is {timer:.2f} {1}", timer, 17, wolla="pure", timer=0.0)
    log.debug("my xala is {0}", xala)
    log.debug("my x is {x}", x=lambda: "ret str")

    for i in range(1_0):
        log.info(f"my range {i}")
        log.debug(f"debug my range {i}")
        if (i % 10000) == 0:
            log.error(f"Error in loop no {i}")

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, syncf)

    await asyncf()
    log.critical("Critical stuff happend")
    log.info("ENDE")
    await asyncio.sleep(0.01)


if __name__ == "__main__":
    t1 = time()
    asyncio.run(main())
    t2 = time()
    duration = t2 - t1
    print("===============================================================================")
    print("duration: %f s" % duration)
    print("===============================================================================")
    logger.error("Duration: %f" % duration, timer=True)
    logger_core.close()
