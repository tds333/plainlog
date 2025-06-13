# SPDX-FileCopyrightText: 2023 Wolfgang Langner <tds333@mailbox.org>
#
# SPDX-License-Identifier: Apache-2.0 OR MIT

"""
Processors useful regardless of the logging framework.
"""

from __future__ import annotations

import contextlib
import sys
import time
from datetime import datetime, timezone
from functools import lru_cache
from multiprocessing import current_process
from os.path import basename, splitext
from pathlib import Path
from threading import current_thread
from typing import Any, Dict, Optional, Protocol

from ._frames import get_frame
from ._recattrs import RecordException
from ._utils import eval_dict, eval_format, eval_lambda_dict, eval_lambda_list, eval_list

STOP_PROCESSING = True
CONTINUE_PROCESSING = False

start_time = datetime.now(timezone.utc)


class ProcessorProtocol(Protocol):
    def __call__(self, record: Dict[str, Any]) -> Optional[bool]: ...


def add_caller_info(record, level=3):
    frame = get_frame(level)
    # name = frame.f_globals["__name__"]
    code = frame.f_code
    file_path = code.co_filename
    file_name = basename(file_path)
    thread = current_thread()
    process = current_process()
    record["function"] = code.co_name
    record["line"] = frame.f_lineno
    record["path"] = Path(file_path)
    record["module"] = splitext(file_name)[0]
    record["file_name"] = file_name
    record["file_path"] = file_path
    record["process_id"] = process.ident
    record["process_name"] = process.name
    record["thread_id"] = thread.ident
    record["thread_name"] = thread.name


def dynamic_name(record):
    frame = get_frame(3)
    name = frame.f_globals["__name__"]
    if name:
        record["name"] = name


def eval_args(record):
    args = record.get("args", [])
    record["args"] = eval_list(args)


def eval_kwargs(record):
    kwargs = record.get("kwargs", {})
    eval_dict(kwargs)


def eval_lambda(record):
    args = record.get("args", [])
    record["args"] = eval_lambda_list(args)

    kwargs = record.get("kwargs", {})
    eval_lambda_dict(kwargs)


def eval_extra(record):
    extra = record.get("extra", {})
    eval_lambda_dict(extra)


def preprocess_exc_info(record):
    kwargs = record.get("kwargs", {})
    exc_info = kwargs.pop("exc_info", False)
    if exc_info:
        type_, value, traceback = sys.exc_info()
        exception = RecordException(type_, value, traceback)
        record["exc_info"] = (type_, value, traceback)
        record["exception"] = exception


def kwargs_to_extra(record):
    kwargs = record.get("kwargs", {})
    if kwargs:
        extra = record.get("extra", {})
        extra.update(kwargs)


def context_to_extra(record):
    context = record.get("context", {})
    if context:
        extra = record.get("extra", {})
        extra.update(context)


def preformat_message(record):
    preformatted = record.get("preformatted", False)
    if preformatted:
        return
    msg = record.get("msg", "")
    args = record.get("args", [])
    kwargs = record.get("kwargs", {})
    if msg and (args or kwargs):
        with contextlib.suppress(Exception):
            record["message"] = eval_format(msg, args, kwargs)
            record["preformatted"] = True


def remove_items(*args):
    def remover(record):
        for arg in args:
            arg = str(arg)
            record.pop(arg, None)

    return remover


def filter_None(record):
    return record["name"] is None


def filter_all(record):
    return STOP_PROCESSING


def filter_by_name(parent):
    def namefilter(record):
        name = record["name"]
        if name is None:
            return STOP_PROCESSING
        return name.startswith(parent)

    return namefilter


def filter_by_level(level_per_module):
    def levelfilter(record):
        name = record["name"]

        while name:
            level = level_per_module.get(name, None)
            if level is False:
                return STOP_PROCESSING
            if level is not None:
                return record["level"].no < level
            if not name:
                return CONTINUE_PROCESSING
            index = name.rfind(".")
            name = name[:index] if index != -1 else ""

    return levelfilter


class FilterList:
    def __init__(self, blacklist, whitelist=None):
        self._whitelist = frozenset() if whitelist is None else frozenset(whitelist)
        self._blacklist = frozenset(blacklist)
        self._partition_cache = {}

    def partition(self, name):
        if name in self._partition_cache:
            return self._partition_cache[name]
        part_set = set()
        parts = name.split(".")
        for i in range(1, len(parts) + 1):
            part_set.add(".".join(parts[:i]))
        self._partition_cache[name] = part_set

        return part_set

    def __call__(self, record):
        name = record["name"]
        name_parts = self.partition(name)

        whitelist = name_parts.isdisjoint(self._whitelist)
        blacklist = not name_parts.isdisjoint(self._blacklist)

        return whitelist and blacklist


class WhitelistLevel:
    def __init__(self, whitelist):
        self._whitelist_names = frozenset(whitelist)
        self._whitelist_levels = whitelist

    @staticmethod
    @lru_cache
    def partition(name):
        part_set = set()
        parts = name.split(".")
        for i in range(1, len(parts) + 1):
            part_set.add(".".join(parts[:i]))

        return part_set

    def __call__(self, record):
        name = record["name"]
        level_no = record["level"].no
        name_parts = self.partition(name)

        whitelisted = not name_parts.isdisjoint(self._whitelist_names)
        if not whitelisted:
            return True
        # else check level
        for name in name_parts:
            level = self._whitelist_levels.get(name)
            if level is not None:
                if level_no < level:
                    return True


class Duration:
    def __init__(self, add_message=True):
        self._starts = {}
        self._add_message = add_message

    def __call__(self, record):
        kwargs = record.get("kwargs", {})
        message = record.get("message", "")
        start = kwargs.get("start", None)
        stop = kwargs.get("stop", None)
        if start:
            self._starts[str(start)] = time.time()
            if not message and self._add_message:
                message = f"Start {start!r}."
                record["message"] = message
        if stop:
            start_time = self._starts.pop(str(stop), None)
            if start_time:
                duration = time.time() - start_time
                # extra = record.get("extra", {})
                # extra["duration_key"] = stop
                # extra["duration"] = duration
                # kwargs["duration_key"] = stop
                kwargs["duration"] = duration
                if not message and self._add_message:
                    message = f"Stop {stop!r}. Duration: {duration:.6f} seconds."
                    record["message"] = message


def elapsed(record):
    record["elapsed"] = datetime.now(timezone.utc) - start_time


# defaults used for core configuration
DEFAULT_PREPROCESSORS = (preprocess_exc_info,)
# DEFAULT_PROCESSORS = (eval_lambda, context_to_extra, kwargs_to_extra, preformat_message)
DEFAULT_PROCESSORS = (context_to_extra, kwargs_to_extra, eval_extra)
