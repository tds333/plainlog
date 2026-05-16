import pytest

from plainlog import logger
from plainlog.configure import _profiles, apply_log_profile


class TestApplyLogProfile:
    @pytest.mark.parametrize("name", (*_profiles.keys(),))
    def test_apply_log_profile(self, name):
        apply_log_profile(name, level="DEBUG")
        assert logger.error("Testmessage") is None
        assert logger.debug("Testmessage") is None
        assert logger.info("Testmessage") is None
        assert logger.warning("Testmessage") is None
        assert logger.critical("Testmessage") is None
        assert logger.exception("Testmessage") is None
