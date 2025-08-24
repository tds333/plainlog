from time import time
import sys

sys.path.append("../src")
from plainlog import logger

from plainlog.warnings import capture_warnings
from plainlog._recattrs import Record

try:
    from string import templatelib
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


capture_warnings(True)

log = logger.new()


def main():
    from plainlog.configure import configure_log

    configure_log("develop", level="DEBUG", reset=True, buffer_size=2)
    processors = (eval_template, *logger.core.processors)
    logger.core.configure(processors=processors)

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
