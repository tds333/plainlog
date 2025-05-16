from time import time, sleep
import sys

import logging

sys.path.append("../src")

log = logging.getLogger("file")

def main():
    local_val = "loc"
    amount = 100_000
    for i in range(amount):
        log.info(f"my local format string {local_val}")
        log.info(f"my local format string {local_val}", extra={"local_val": "local", "ohter": 1})
        log.warning("mywarning")
        log.debug("my debug")


    log.info("BEVORE LOOP")
    for i in range(amount):
        log.info(f"my range {i}")
        log.debug("debug my range")
    log.info("AFTER LOOP")


if __name__ == "__main__":
    log.setLevel(logging.DEBUG)

    # create console handler and set level to debug
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)

    # create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # add formatter to ch
    ch.setFormatter(formatter)

    # add ch to logger
    log.addHandler(ch)
    #log.addHandler(logging.NullHandler())
    t1 = time()
    #cProfile.run("main2()")
    main()
    t2 = time()
    duration = t2 - t1
    print("===============================================================================")
    print("duration: %f s" % duration)
    print("===============================================================================")
    log.critical(f"Duration: {duration}")
    #logger.close()
    #logger.close()
