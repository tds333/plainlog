# SPDX-FileCopyrightText: 2023 Wolfgang Langner <tds333@mailbox.org>
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
from os import environ

PLAINLOG_LEVEL: str = environ.get("PLAINLOG_LEVEL", "NOTSET")
PLAINLOG_PROFILE: str = environ.get("PLAINLOG_PROFILE", "default")

DEFAULT_WAIT_TIMEOUT = 5.0  # in seconds
