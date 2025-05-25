from multiprocessing import Pool, Process
from plainlog import logger
from time import sleep

log = logger.new()
glog = log


def init_log():
    from plainlog import logger

    logger.info("in init_log")


def f(x):
    log.info("in f")
    return x * x


def main():
    with Pool(5, initializer=init_log) as p:
        log = logger.new()
        log.info("in pool")
        print(id(log))
        print(id(log._core))
        print(p.map(f, [1, 2, 3]))


def f_name(name, log=None):
    log = glog if log is None else log
    print(id(log))
    print(id(log._core))
    log.info("in f_name")
    print("hello", name)


def main_name():
    p = Process(target=f_name, args=("bob",))
    log.info("in main_name")
    print(id(log))
    print(id(log._core))
    p.start()
    p.join()


if __name__ == "__main__":
    # main_name()
    main()
