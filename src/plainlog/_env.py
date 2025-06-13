# SPDX-FileCopyrightText: 2023 Wolfgang Langner <tds333@mailbox.org>
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
from os import environ

PLAINLOG_LEVEL = environ.get("PLAINLOG_LEVEL", "DEBUG")
PLAINLOG_PROFILE = environ.get("PLAINLOG_PROFILE", "default")

DEFAULT_WAIT_TIMEOUT = 5.0  # in seconds
