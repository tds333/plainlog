# imported module

from plainlog import logger

toplevel_log = logger.new()


def fun():
    log = logger.new()
    log.debug("in function fun")


class MyImClass:

    def __init__(self):
        self.log = logger.new()
        self.logc = logger.new(self.__class__.__qualname__)

    def do(self):
        self.log.debug("log in MyImClass.do")
        self.logc.info("logc in MyImClass.do")


def run():
    fun()
    m = MyImClass()
    m.do()
    toplevel_log.debug("immod top level")
