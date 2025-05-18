import pytest
from plainlog import logger
from plainlog.configure import configure_log, _profiles


class TestConfigureLog:
    @pytest.mark.parametrize("name", (*_profiles.keys(),))
    def test_configure_log(self, name):
        configure_log(name)
        assert logger.info("Testmessage") is None
