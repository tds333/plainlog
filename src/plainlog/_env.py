from os import environ

PLAINLOG_LEVEL: str = environ.get("PLAINLOG_LEVEL", "NOTSET")
PLAINLOG_PROFILE: str = environ.get("PLAINLOG_PROFILE", "default")

DEFAULT_WAIT_TIMEOUT = 5.0  # in seconds
