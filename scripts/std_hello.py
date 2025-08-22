#!/usr/bin/env -S uv run --script
# ruff: noqa
# type: ignore
import sys

import plainlog.std
import logging

print(sys.path)


def main():
    root = logging.getLogger("root")
    root.setLevel("DEBUG")
    root.addHandler(plainlog.std.StdInterceptHandler())
    root = logging.getLogger("root")
    root.setLevel("DEBUG")
    root.addHandler(plainlog.std.StdInterceptHandler())
    log = logging.getLogger("bla")
    try:
        1 / 0
    except Exception:
        log.exception("Got an error")
        pass
    log.debug("bla log")
    log.log(40, "mydata %s %d", "a1", 10)
    log.info("my information %d %s", 10, "info", extra={"add_info": "more bla"})

    log.error("This is an error %s", "special error")
    log.warning("warning")
    # log.warning("with extra", somevar="somevar", second_extr=10)

    bluff_log = logging.getLogger("bluff")
    bluff_log.debug("other logger")
    name_log = logging.getLogger(__name__)
    name_log.info("named logger")
    name_log.debug("with extra %f", 1.0, extra=dict(somevar="somevar", second_extr=10))


if __name__ == "__main__":
    main()
