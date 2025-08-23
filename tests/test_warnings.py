from plainlog.warnings import capture_warnings


def test_warnings():
    capture_warnings(True)
    capture_warnings(False)
