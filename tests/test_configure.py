import pytest

from plainlog import logger
from plainlog.configure import _profiles, add_profile, apply_log_profile


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


def test_apply_log_profile_default():
    apply_log_profile(level="DEBUG")
    assert logger.error("ok") is None


def test_apply_log_profile_invalid_name():
    with pytest.raises(ValueError, match="not a valid log profile"):
        apply_log_profile(name="nonexistent")


def test_add_profile_new():
    _profiles.pop("_test_custom", None)

    def custom(level=None, **kwargs):
        pass

    result = add_profile("_test_custom", custom)
    assert result is True
    assert "_test_custom" in _profiles
    apply_log_profile(name="_test_custom")
    _profiles.pop("_test_custom", None)


def test_add_profile_duplicate():
    def stub(level=None, **kwargs):
        pass

    result = add_profile("default", stub)
    assert result is False
