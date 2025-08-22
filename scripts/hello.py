from time import time, sleep
import sys

sys.path.append("../src")
from plainlog import logger, logger_core
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

capture_warnings(True)

log = logger.new()


def val():
    return "from val function"


def pa(record):
    record["my special info"] = 0
    return True


def frame_patcher(record):
    frame = sys._getframe()
    record["frame"] = frame


def timer():
    return time()


def duration_calc(start=time()):
    duration = time() - start
    return duration


start = time()


def elapsed():
    duration = time() - start
    return duration


def messager(record):
    print(f"{record['datetime'].isoformat()} {record['message']}")
    # print(f"{record['datetime']:%H:%M} {record['message']}")
    # print(record["datetime"], record["message"])


async def amessager(record):
    print(f"amessager: {record}")
    # print(f"{record['datetime']:%H:%M} {record['message']}")
    # print(record["datetime"], record["message"])


class SpecPrint:
    def __init__(self, name=None):
        self.name = name
        self.stream = sys.stdout

    def __call__(self, record):
        # print(f"{record['level']}: {record['datetime']:%H:%Mh} [{record['name']}] {record['message']} {record['elapsed']}")
        self.stream.write(
            f"{record['level']}: {record['datetime']:%H:%Mh} [{record['name']}] {record['message']} {record['elapsed']} {record['extra']}\n"
        )

    def __repr__(self):
        return f"SpecPrint({self.name})"

    def close(self):
        self.stream.flush()


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
    log = logger.new(extra={"elapsed": lambda: elapsed()})
    first_log = log
    log.debug("hello")

    log = log.bind(bla=5)
    log.info("mit extra")

    log = log.new(processors=pa)
    log.warning("warn me")

    log = first_log

    try:
        1 / 0
    except ZeroDivisionError:
        log.exception("Error")

    log.debug("my time is ", wolla="pure")
    # log = log.new(extra={})
    hr = logger_core.add(print)
    print(hr)
    log.debug("fsdfsdfsdf")
    logger_core.remove(hr.name)

    local_val = "10045 sdf"
    log.info(f"my local format string {local_val}")
    log.info("my local format string {local_val}", local_val=5)
    log.info("timer output", timer=lambda: timer(), timer_func=timer, timer_result=timer())
    log.info("print output", pval=lambda: repr(hr))
    log.debug("duration={duration}", duration=lambda: duration_calc(time()))
    log.debug("start duration={duration}", duration=lambda: duration_calc())
    log.debug("d start, elapsed")
    log.debug("s", start_timer="one")
    log.debug("", stop_timer="one")

    lc = LoggerClass()

    lc.do()

    log.info("BEVORE LOOP")
    for i in range(5):
        log.info(f"my range {i}")
        log.debug("debug my range")
    log.info("AFTER LOOP")
    log = log.new(__name__)
    log.error("LOLA")
    # print("sleep")
    # sleep(0.8)


def main2():
    from plainlog.configure import configure_log

    # configure_log("develop", level="DEBUG", reset=True, buffer_size=2)
    configure_log("develop", level="DEBUG", reset=True, buffer_size=2)
    log = logger.new()
    log.debug("hello")
    log.warning("some warning")

    log = log.bind(bla=5)
    log.context(special_context="my context")
    log.info("mit extra")

    try:
        1 / 0
    except ZeroDivisionError:
        log.exception("Error")

    log.debug("my time is ", wolla="pure")

    for i in range(5):
        log.info(f"my range {i}")
        log.debug(f"debug my range {i}")
        if (i % 100) == 0:
            log.error(f"Error in loop no {i}")
    log.critical("Critical stuff happend")
    log.info("ENDE")


def main4():
    global log
    from plainlog.configure import configure_log

    handler_type = "develop"
    configure_log(handler_type, level="DEBUG")
    # log = logger.name("test")
    # log = logger.name().processor(FilterList(blacklist=["mymodule"], whitelist=["mymodule.class.function"]))
    log.debug(f"Start {__name__}", start=__name__)

    log.info("Server starting...")
    log.info("Listening on http://127.0.0.1:8080")

    log.info("GET /index.html 200 1298", method="GET")
    log.info("GET /imgs/backgrounds/back1.jpg 200 54386")
    log.info("GET /css/styles.css 200 54386")
    log.warning("GET /favicon.ico 404 242")
    log = logger.new()

    log.debug(
        "JSONRPC request\n--> %r\n<-- %r"
        % (
            {
                "version": "1.1",
                "method": "confirmFruitPurchase",
                "params": [["apple", "orange", "mangoes", "pomelo"], 1.123],
                "id": "194521489",
            },
            {"version": "1.1", "result": True, "error": None, "id": "194521489"},
        )
    )
    log.debug(
        "Loading configuration file /adasd/asdasd/qeqwe/qwrqwrqwr/sdgsdgsdg/werwerwer/dfgerert/ertertert/ertetert/werwerwer"
    )
    log.error("Unable to find 'pomelo' in database!")
    log.info("POST /jsonrpc/ 200 65532")
    log.info("POST /admin/ 401 42234")
    log.warning("password was rejected for admin site.")

    def divide() -> None:
        logg = log.new()
        number = 1
        divisor = 0
        foos = ["foo"] * 100
        logg.debug("in divide")
        try:
            number / divisor
        except:
            logg.exception("An error of some kind occurred!")

    divide()
    log.critical("Out of memory!")
    log.info("Server exited with code=-1")
    log.info("[bold]EXITING...[/bold]", markup=True, more="some longer text")
    log.info("keys", val, more="more")

    log = log.bind(rquest="sunrise", current_id=500)
    log.info("start request")
    log.info("end request")
    log = log.unbind("current_id")
    log.debug("no id in request?")
    log.new(name="mymodule.class.function", extra={}).info("from main function")
    log.new("mymodule.class", extra={}).info("from main class")
    log.new("mymodulex", extra={}).info("from main mymodulex")
    log.new("LoggerClassX").info("name test")
    log.debug("Stop {stop!r}, duration: {duration:.6f}", stop=__name__, duration=1)
    log.info("", start="bla")
    log.info("", stop="bla")
    log("INFO", start="simple")
    log("INFO", stop="simple")
    log = log.unbind("rquest")
    # for i in range(10_000_000):
    #     log.debug(str(i))
    lc = LoggerClass()
    lc.do()
    lc.do_context()
    log = log.new(preprocessors=filter_by_name("LoggerClass"))
    log.debug("with")
    log.new("LoggerClass").info("should filter")
    with log.contextualize(some_ctx="my context info"):
        log.info("with context")
    log.context(first_context="first one")
    token = log.context(my_own="special set context")
    myown_token = log.context(my_own2="special set context 2")
    token3 = log.context(my_own3="special set context 3")
    log.debug("with my context")
    log.reset_context(myown_token)
    log.debug("with my context")
    log.reset_context(token3)
    log.debug("with my context before reset 3")
    log.reset_context(token)
    log.info("with first context")
    log.context()
    log.info("with new context clean")
    log("I", "short info")
    log("W", "notset")
    log.info("ENDE")


def main5():
    global log
    from plainlog.configure import configure_log

    handler_type = "develop"
    # configure_log(handler_type, level="DEBUG")
    from immod import run

    log.debug(f"Start in main5")
    run()
    log.debug(f"after run")


if __name__ == "__main__":
    from plainlog.warnings import capture_warnings

    capture_warnings(True)
    import cProfile

    t1 = time()
    # cProfile.run("main2()")
    # main()
    main2()
    # main3()
    # main4()
    # main5()
    # main()
    t2 = time()
    duration = t2 - t1
    print("===============================================================================")
    print("duration: %f s" % duration)
    print("===============================================================================")
    logger.error("Duration: %f" % duration, timer=True)
    # logger.close()
    # logger.close()
