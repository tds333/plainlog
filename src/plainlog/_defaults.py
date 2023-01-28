# SPDX-FileCopyrightText: 2023 Wolfgang Langner <tds333@mailbox.org>
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
from os import environ


def env(key, type_, default=None):
    if key not in environ:
        return default

    val = environ[key]

    if type_ == str:
        return val
    elif type_ == bool:
        if val.lower() in ["1", "true", "yes", "y", "ok", "on"]:
            return True
        if val.lower() in ["0", "false", "no", "n", "nok", "off"]:
            return False
        raise ValueError(f"Invalid environment variable {key!r} (expected a boolean): {val!r}")
    elif type_ == int:
        try:
            return int(val)
        except ValueError:
            raise ValueError(f"Invalid environment variable {key!r} (expected an integer): {val!r}") from None


PLAINLOG_AUTOINIT = env("PLAINLOG_AUTOINIT", bool, True)
PLAINLOG_LEVEL =    env("PLAINLOG_LEVEL", str, "DEBUG")
PLAINLOG_PROFILE =  env("PLAINLOG_PROFILE", str, "default")
