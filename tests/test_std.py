import logging
from plainlog import logger
from plainlog.std import set_as_root_handler


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
