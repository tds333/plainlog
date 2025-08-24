# SPDX-FileCopyrightText: 2023 Wolfgang Langner <tds333@mailbox.org>
#
# SPDX-License-Identifier: Apache-2.0 OR MIT

"""
Processors useful regardless of the logging framework.
"""

import contextlib
import sys
import time
from datetime import datetime, timezone
from functools import lru_cache
from multiprocessing import current_process
from os.path import basename, splitext
from pathlib import Path
from threading import current_thread
from typing import Protocol, Callable

from ._frames import get_frame
from ._recattrs import RecordException, Record
from ._utils import eval_dict, eval_format, eval_lambda_dict


start_time: datetime = datetime.now(timezone.utc)


class ProcessorProtocol(Protocol):
    def __call__(self, record: Record) -> Record: ...


def add_caller_info(record: Record, level=3) -> Record:
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

    return record


def dynamic_name(record: Record) -> Record:
    frame = get_frame(3)
    name = frame.f_globals["__name__"]
    if name:
        record["name"] = name

    return record


def eval_kwargs(record: Record) -> Record:
    kwargs = record.get("kwargs", {})
    eval_dict(kwargs)

    return record


def eval_lambda(record: Record) -> Record:
    kwargs = record.get("kwargs", {})
    eval_lambda_dict(kwargs)

    return record


def eval_extra(record: Record) -> Record:
    extra = record.get("extra", {})
    eval_lambda_dict(extra)

    return record


def preprocess_exc_info(record: Record) -> Record:
    kwargs = record.get("kwargs", {})
    exc_info = kwargs.pop("exc_info", False)
    if exc_info:
        type_, value, traceback = sys.exc_info()
        exception = RecordException(type_, value, traceback)
        # record["exc_info"] = (type_, value, traceback)
        record["exception"] = exception

    return record


def kwargs_to_extra(record: Record) -> Record:
    kwargs = record.get("kwargs", {})
    if kwargs:
        extra = record.get("extra", {})
        extra.update(kwargs)

    return record


def context_to_extra(record: Record) -> Record:
    context = record.get("context", {})
    if context:
        extra = record.get("extra", {})
        extra.update(context)

    return record


def preformat_message(record: Record) -> Record:
    preformatted = record.get("preformatted", False)
    if preformatted:
        return record
    msg = record.get("msg", "")
    kwargs = record.get("kwargs", {})
    if msg and kwargs:
        with contextlib.suppress(Exception):
            record["message"] = eval_format(msg, kwargs)
            record["preformatted"] = True

    return record


def remove_items(*args) -> Callable:
    def remover(record: Record) -> Record:
        for arg in args:
            arg = str(arg)
            record.pop(arg, None)
        return record

    return remover


def filter_None(record: Record) -> Record:
    if record["name"] is None:
        return {}
    return record


def filter_all(record: Record) -> Record:
    return {}


def filter_by_name(parent) -> Callable:
    def namefilter(record: Record) -> Record:
        name = record["name"]
        if name is None:
            return {}
        elif name.startswith(parent):
            return {}
        return record

    return namefilter


def filter_by_level(level_per_module) -> Callable:
    def levelfilter(record: Record) -> Record:
        name = record["name"]

        while name:
            level = level_per_module.get(name, None)
            if level is False:
                return {}
            if level is not None:
                if record["level"].no < level:
                    return {}
            if not name:
                return record
            index = name.rfind(".")
            name = name[:index] if index != -1 else ""

        return record

    return levelfilter


class FilterList:
    def __init__(self, blacklist, whitelist=None) -> None:
        self._whitelist = frozenset() if whitelist is None else frozenset(whitelist)
        self._blacklist = frozenset(blacklist)
        self._partition_cache: dict = {}

    def partition(self, name: str) -> set:
        if name in self._partition_cache:
            return self._partition_cache[name]
        part_set = set()
        parts = name.split(".")
        for i in range(1, len(parts) + 1):
            part_set.add(".".join(parts[:i]))
        self._partition_cache[name] = part_set

        return part_set

    def __call__(self, record: Record) -> Record:
        name = record["name"]
        name_parts = self.partition(name)

        whitelist = name_parts.isdisjoint(self._whitelist)
        blacklist = not name_parts.isdisjoint(self._blacklist)

        if whitelist and blacklist:
            return {}
        return record


class WhitelistLevel:
    def __init__(self, whitelist) -> None:
        self._whitelist_names = frozenset(whitelist)
        self._whitelist_levels = whitelist

    @staticmethod
    @lru_cache
    def partition(name) -> set:
        part_set = set()
        parts = name.split(".")
        for i in range(1, len(parts) + 1):
            part_set.add(".".join(parts[:i]))

        return part_set

    def __call__(self, record: Record) -> Record:
        name = record["name"]
        level_no = record["level"].no
        name_parts = self.partition(name)

        whitelisted: bool = not name_parts.isdisjoint(self._whitelist_names)
        if not whitelisted:
            return {}
        # else check level
        for name in name_parts:
            level = self._whitelist_levels.get(name)
            if level is not None:
                if level_no < level:
                    return {}

        return record


class Duration:
    def __init__(self, add_message=True) -> None:
        self._starts: dict = {}
        self._add_message = add_message

    def __call__(self, record: Record) -> Record:
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
        return record


def elapsed(record) -> None:
    record["elapsed"] = datetime.now(timezone.utc) - start_time
    return record


# defaults used for core configuration
DEFAULT_PREPROCESSORS = (preprocess_exc_info,)
# DEFAULT_PROCESSORS = (eval_lambda, context_to_extra, kwargs_to_extra, preformat_message)
DEFAULT_PROCESSORS = (context_to_extra, kwargs_to_extra, eval_extra)
