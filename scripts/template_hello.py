# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "plainlog>=0.3.0",
# ]
#
# [tool.uv.sources]
# plainlog = { path = "../" }
# ///

import sys
from time import time

from plainlog import logger
from plainlog._base import Record
from plainlog.handlers import DevelopHandler
from plainlog.warnings import capture_warnings

try:
    from string import templatelib  # ty:ignore[unresolved-import]
except ImportError:
    print("Python >=3.14 required to use t-strings.")
    sys.exit(1)


def f(template: templatelib.Template) -> str:
    parts = []
    for item in template:
        match item:
            case str() as s:
                parts.append(s)
            case templatelib.Interpolation(value, _, conversion, format_spec):
                value = templatelib.convert(value, conversion)
                value = format(value, format_spec)
                parts.append(value)
    return "".join(parts)


def eval_template(record: Record) -> Record:
    msg = record["msg"]
    record["message"] = f(msg)
    record["preformatted"] = True
    return record


class EvalTemplatHandler(DevelopHandler):
    def process(self, record):
        record = eval_template(record)
        return super().process(record)


capture_warnings(True)

log = logger.new()


def main():
    logger.core.configure(handler=EvalTemplatHandler(), level="DEBUG")

    name = "My name"
    log = logger.new()
    log.debug(t"hello {name}")


if __name__ == "__main__":
    from plainlog.warnings import capture_warnings

    capture_warnings(True)

    t1 = time()
    main()
    t2 = time()
    duration = t2 - t1
    logger.error("Duration: %f" % duration, timer=True)
