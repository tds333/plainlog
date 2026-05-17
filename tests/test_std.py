import logging

from plainlog._logger import logger_core
from plainlog.std import StdInterceptHandler, set_as_root_handler


def test_set_as_root_handler(thandler):
    handler = set_as_root_handler(level="DEBUG")
    root = logging.getLogger(name="root")
    level_old = root.getEffectiveLevel()
    try:
        root.setLevel("DEBUG")
        message = "This is stdlog debug test."
        root.debug(message)
        record = thandler.first()

        assert record["msg"] == message
    finally:
        root.setLevel(level_old)
        root.removeHandler(handler)


def test_std_intercept_handler_level_filtering(thandler):
    root = logging.getLogger(name="root")

    for h in list(root.handlers):
        if isinstance(h, StdInterceptHandler):
            root.removeHandler(h)

    handler = StdInterceptHandler(level=logging.WARNING)
    level_old = root.getEffectiveLevel()
    try:
        root.setLevel("DEBUG")
        root.addHandler(handler)

        record_info = root.makeRecord(
            "root", logging.INFO, "test.py", 1, "direct info", (), None,
        )
        handler.emit(record_info)
        logger_core.wait_for_processed()
        assert not thandler.records

        root.warning("should pass")
        logger_core.wait_for_processed()
        assert thandler.records
    finally:
        root.setLevel(level_old)
        root.removeHandler(handler)
