# /// script
# dependencies = [
#   "plainlog",
# ]
# ///

from time import time

from plainlog import logger

# from plainlog._rich_handler import RichHandler

# capture_warnings(True)

log = logger.new()


class LoggerClass:
    # clog = logger.new(name=__qualname__)
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


def main():
    local_val = "loc"
    amount = 100_000
    for _ in range(amount):
        log.info(f"my local format string {local_val}")
        log.info(f"my local format string {local_val}", some_extra="yeah", local_val=1)
        log.warning("mywarning")
        log.debug("my debug")

    log.info("BEVORE LOOP")
    for i in range(amount):
        log.info(f"my range {i}")
        log.debug("debug my range")
    log.info("AFTER LOOP")


if __name__ == "__main__":
    # capture_warnings(True)

    # configure_log("fast", level="DEBUG")
    # configure_log("empty", level="DEBUG")
    t1 = time()
    # cProfile.run("main2()")
    main()
    t2 = time()
    duration = t2 - t1
    print(
        "==============================================================================="
    )
    print("duration: %f s" % duration)
    print(
        "==============================================================================="
    )
    logger.critical("Duration: %f" % duration, timer=True)
    # logger.close()
    # logger.close()
