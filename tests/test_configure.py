import pytest
from plainlog import logger
from plainlog.configure import configure_log, _profiles


class TestConfigureLog:
    @pytest.mark.parametrize("name", (*_profiles.keys(),))
    def test_configure_log(self, name):
        configure_log(name, level="DEBUG")
        assert logger.error("Testmessage") is None
        assert logger.debug("Testmessage") is None
        assert logger.info("Testmessage") is None
        assert logger.warning("Testmessage") is None
        assert logger.critical("Testmessage") is None
        assert logger.exception("Testmessage") is None
