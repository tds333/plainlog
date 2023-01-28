# SPDX-FileCopyrightText: 2023 Wolfgang Langner <tds333@mailbox.org>
#
# SPDX-License-Identifier: Apache-2.0 OR MIT

# mostly copied from loguru

import decimal
import glob
import numbers
import os
import re
import shutil
import string
from functools import partial
from stat import ST_DEV, ST_INO
from datetime import datetime, timezone, timedelta
from time import localtime, strftime

from .formatters import SimpleFormatter


def aware_now():
    now = datetime.now()
    timestamp = now.timestamp()
    local = localtime(timestamp)

    try:
        seconds = local.tm_gmtoff
        zone = local.tm_zone
    except AttributeError:
        offset = datetime.fromtimestamp(timestamp) - datetime.utcfromtimestamp(timestamp)
        seconds = offset.total_seconds()
        zone = strftime("%Z")

    tzinfo = timezone(timedelta(seconds=seconds), zone)

    return datetime.combine(now.date(), now.time().replace(tzinfo=tzinfo))


class FileDateFormatter:
    def __init__(self, datetime=None):
        self.datetime = datetime or aware_now()

    def __format__(self, spec):
        if not spec:
            spec = "%Y-%m-%d_%H-%M-%S_%f"
        return self.datetime.__format__(spec)


def load_ctime_functions():
    # if os.name == "nt":
    #     import win32_setctime

    #     def get_ctime_windows(filepath):
    #         return os.stat(filepath).st_ctime

    #     def set_ctime_windows(filepath, timestamp):
    #         if not win32_setctime.SUPPORTED:
    #             return

    #         try:
    #             win32_setctime.setctime(filepath, timestamp)
    #         except (OSError, ValueError):
    #             pass

    #     return get_ctime_windows, set_ctime_windows

    if hasattr(os.stat_result, "st_birthtime"):

        def get_ctime_macos(filepath):
            return os.stat(filepath).st_birthtime

        def set_ctime_macos(filepath, timestamp):
            pass

        return get_ctime_macos, set_ctime_macos

    elif hasattr(os, "getxattr") and hasattr(os, "setxattr"):

        def get_ctime_linux(filepath):
            try:
                return float(os.getxattr(filepath, b"user.plainlog_crtime"))
            except OSError:
                return os.stat(filepath).st_mtime

        def set_ctime_linux(filepath, timestamp):
            try:
                os.setxattr(filepath, b"user.plainlog_crtime", str(timestamp).encode("ascii"))
            except OSError:
                pass

        return get_ctime_linux, set_ctime_linux

    def get_ctime_fallback(filepath):
        return os.stat(filepath).st_mtime

    def set_ctime_fallback(filepath, timestamp):
        pass

    return get_ctime_fallback, set_ctime_fallback


get_ctime, set_ctime = load_ctime_functions()


class Frequencies:
    @staticmethod
    def hourly(t):
        dt = t + datetime.timedelta(hours=1)
        return dt.replace(minute=0, second=0, microsecond=0)

    @staticmethod
    def daily(t):
        dt = t + datetime.timedelta(days=1)
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)

    @staticmethod
    def weekly(t):
        dt = t + datetime.timedelta(days=7 - t.weekday())
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)

    @staticmethod
    def monthly(t):
        if t.month == 12:
            y, m = t.year + 1, 1
        else:
            y, m = t.year, t.month + 1
        return t.replace(year=y, month=m, day=1, hour=0, minute=0, second=0, microsecond=0)

    @staticmethod
    def yearly(t):
        y = t.year + 1
        return t.replace(year=y, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)


def parse_size(size):
    size = size.strip()
    reg = re.compile(r"([e\+\-\.\d]+)\s*([kmgtpezy])?(i)?(b)", flags=re.I)

    match = reg.fullmatch(size)

    if not match:
        return None

    s, u, i, b = match.groups()

    try:
        s = float(s)
    except ValueError as e:
        raise ValueError("Invalid float value while parsing size: '%s'" % s) from e

    u = "kmgtpezy".index(u.lower()) + 1 if u else 0
    i = 1024 if i else 1000
    b = {"b": 8, "B": 1}[b] if b else 1
    size = s * i**u / b

    return size


def parse_duration(duration):
    duration = duration.strip()
    reg = r"(?:([e\+\-\.\d]+)\s*([a-z]+)[\s\,]*)"

    units = [
        ("y|years?", 31536000),
        ("months?", 2628000),
        ("w|weeks?", 604800),
        ("d|days?", 86400),
        ("h|hours?", 3600),
        ("min(?:ute)?s?", 60),
        ("s|sec(?:ond)?s?", 1),
        ("ms|milliseconds?", 0.001),
        ("us|microseconds?", 0.000001),
    ]

    if not re.fullmatch(reg + "+", duration, flags=re.I):
        return None

    seconds = 0

    for value, unit in re.findall(reg, duration, flags=re.I):
        try:
            value = float(value)
        except ValueError as e:
            raise ValueError("Invalid float value while parsing duration: '%s'" % value) from e

        try:
            unit = next(u for r, u in units if re.fullmatch(r, unit, flags=re.I))
        except StopIteration:
            raise ValueError("Invalid unit value while parsing duration: '%s'" % unit) from None

        seconds += value * unit

    return datetime.timedelta(seconds=seconds)


def parse_frequency(frequency):
    frequencies = {
        "hourly": Frequencies.hourly,
        "daily": Frequencies.daily,
        "weekly": Frequencies.weekly,
        "monthly": Frequencies.monthly,
        "yearly": Frequencies.yearly,
    }
    frequency = frequency.strip().lower()
    return frequencies.get(frequency, None)


def parse_day(day):
    days = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }
    day = day.strip().lower()
    if day in days:
        return days[day]
    elif day.startswith("w") and day[1:].isdigit():
        day = int(day[1:])
        if not 0 <= day < 7:
            raise ValueError("Invalid weekday value while parsing day (expected [0-6]): '%d'" % day)
    else:
        day = None

    return day


def parse_time(time):
    time = time.strip()
    reg = re.compile(r"^[\d\.\:]+\s*(?:[ap]m)?$", flags=re.I)

    if not reg.match(time):
        return None

    formats = [
        "%H",
        "%H:%M",
        "%H:%M:%S",
        "%H:%M:%S.%f",
        "%I %p",
        "%I:%M %S",
        "%I:%M:%S %p",
        "%I:%M:%S.%f %p",
    ]

    for format_ in formats:
        try:
            dt = datetime.datetime.strptime(time, format_)
        except ValueError:
            pass
        else:
            return dt.time()

    raise ValueError("Unrecognized format while parsing time: '%s'" % time)


def parse_daytime(daytime):
    daytime = daytime.strip()
    reg = re.compile(r"^(.*?)\s+at\s+(.*)$", flags=re.I)

    match = reg.match(daytime)
    if match:
        day, time = match.groups()
    else:
        day = time = daytime

    try:
        day = parse_day(day)
        if match and day is None:
            raise ValueError
    except ValueError as e:
        raise ValueError("Invalid day while parsing daytime: '%s'" % day) from e

    try:
        time = parse_time(time)
        if match and time is None:
            raise ValueError
    except ValueError as e:
        raise ValueError("Invalid time while parsing daytime: '%s'" % time) from e

    if day is None and time is None:
        return None

    return day, time


def generate_rename_path(root, ext, creation_time):
    creation_datetime = datetime.datetime.fromtimestamp(creation_time)
    date = FileDateFormatter(creation_datetime)

    renamed_path = "{}.{}{}".format(root, date, ext)
    counter = 1

    while os.path.exists(renamed_path):
        counter += 1
        renamed_path = "{}.{}.{}{}".format(root, date, counter, ext)

    return renamed_path


class Compression:
    @staticmethod
    def add_compress(path_in, path_out, opener, **kwargs):
        with opener(path_out, **kwargs) as f_comp:
            f_comp.add(path_in, os.path.basename(path_in))

    @staticmethod
    def write_compress(path_in, path_out, opener, **kwargs):
        with opener(path_out, **kwargs) as f_comp:
            f_comp.write(path_in, os.path.basename(path_in))

    @staticmethod
    def copy_compress(path_in, path_out, opener, **kwargs):
        with open(path_in, "rb") as f_in:
            with opener(path_out, **kwargs) as f_out:
                shutil.copyfileobj(f_in, f_out)

    @staticmethod
    def compression(path_in, ext, compress_function):
        path_out = "{}{}".format(path_in, ext)

        if os.path.exists(path_out):
            creation_time = get_ctime(path_out)
            root, ext_before = os.path.splitext(path_in)
            renamed_path = generate_rename_path(root, ext_before + ext, creation_time)
            os.rename(path_out, renamed_path)
        compress_function(path_in, path_out)
        os.remove(path_in)


class Retention:
    @staticmethod
    def retention_count(logs, number):
        def key_log(log):
            return (-os.stat(log).st_mtime, log)

        for log in sorted(logs, key=key_log)[number:]:
            os.remove(log)

    @staticmethod
    def retention_age(logs, seconds):
        t = datetime.datetime.now().timestamp()
        for log in logs:
            if os.stat(log).st_mtime <= t - seconds:
                os.remove(log)


class Rotation:
    @staticmethod
    def forward_day(t):
        return t + datetime.timedelta(days=1)

    @staticmethod
    def forward_weekday(t, weekday):
        while True:
            t += datetime.timedelta(days=1)
            if t.weekday() == weekday:
                return t

    @staticmethod
    def forward_interval(t, interval):
        return t + interval

    @staticmethod
    def rotation_size(message, file, size_limit):
        file.seek(0, 2)
        return file.tell() + len(message) > size_limit

    class RotationTime:
        def __init__(self, step_forward, time_init=None):
            self._step_forward = step_forward
            self._time_init = time_init
            self._limit = None

        def __call__(self, message, file):
            if self._limit is None:
                filepath = os.path.realpath(file.name)
                creation_time = get_ctime(filepath)
                set_ctime(filepath, creation_time)
                start_time = limit = datetime.datetime.fromtimestamp(creation_time)
                if self._time_init is not None:
                    limit = limit.replace(
                        hour=self._time_init.hour,
                        minute=self._time_init.minute,
                        second=self._time_init.second,
                        microsecond=self._time_init.microsecond,
                    )
                if limit <= start_time:
                    limit = self._step_forward(limit)
                self._limit = limit

            record_time = message.record["time"].replace(tzinfo=None)
            if record_time >= self._limit:
                while self._limit <= record_time:
                    self._limit = self._step_forward(self._limit)
                return True
            return False


class FileHandler:
    def __init__(
        self,
        path,
        *,
        formatter=None,
        rotation=None,
        retention=None,
        compression=None,
        delay=False,
        watch=False,
        mode="a",
        buffering=1,
        encoding="utf8",
        **kwargs
    ):
        self.encoding = encoding
        self._formatter = SimpleFormatter() if formatter is None else formatter

        self._kwargs = {**kwargs, "mode": mode, "buffering": buffering, "encoding": self.encoding}
        self._path = str(path)

        self._glob_patterns = self._make_glob_patterns(self._path)
        self._rotation_function = self._make_rotation_function(rotation)
        self._retention_function = self._make_retention_function(retention)
        self._compression_function = self._make_compression_function(compression)

        self._file = None
        self._file_path = None

        self._watch = watch
        self._file_dev = -1
        self._file_ino = -1
        self.terminator = "\n"

        if not delay:
            path = self._create_path()
            self._create_dirs(path)
            self._create_file(path)

    def __call__(self, record):
        message = self._formatter(record)
        self.write(message)

    def write(self, message):
        if self._file is None:
            path = self._create_path()
            self._create_dirs(path)
            self._create_file(path)

        if self._watch:
            self._reopen_if_needed()

        if self._rotation_function is not None and self._rotation_function(message, self._file):
            self._terminate_file(is_rotating=True)

        self._file.write(message)
        self._file.write(self.terminator)

    def close(self):
        if self._watch:
            self._reopen_if_needed()

        self._terminate_file(is_rotating=False)

    def _create_path(self):
        path = self._path.format_map({"time": FileDateFormatter()})
        return os.path.abspath(path)

    def _create_dirs(self, path):
        dirname = os.path.dirname(path)
        os.makedirs(dirname, exist_ok=True)

    def _create_file(self, path):
        self._file = open(path, **self._kwargs)
        self._file_path = path

        if self._watch:
            fileno = self._file.fileno()
            result = os.fstat(fileno)
            self._file_dev = result[ST_DEV]
            self._file_ino = result[ST_INO]

    def _close_file(self):
        self._file.flush()
        self._file.close()

        self._file = None
        self._file_path = None
        self._file_dev = -1
        self._file_ino = -1

    def _reopen_if_needed(self):
        # Implemented based on standard library:
        # https://github.com/python/cpython/blob/cb589d1b/Lib/logging/handlers.py#L486
        if not self._file:
            return

        filepath = self._file_path

        try:
            result = os.stat(filepath)
        except FileNotFoundError:
            result = None

        if not result or result[ST_DEV] != self._file_dev or result[ST_INO] != self._file_ino:
            self._close_file()
            self._create_dirs(filepath)
            self._create_file(filepath)

    def _terminate_file(self, *, is_rotating=False):
        old_path = self._file_path

        if self._file is not None:
            self._close_file()

        if is_rotating:
            new_path = self._create_path()
            self._create_dirs(new_path)

            if new_path == old_path:
                creation_time = get_ctime(old_path)
                root, ext = os.path.splitext(old_path)
                renamed_path = generate_rename_path(root, ext, creation_time)
                os.rename(old_path, renamed_path)
                old_path = renamed_path

        if is_rotating or self._rotation_function is None:
            if self._compression_function is not None and old_path is not None:
                self._compression_function(old_path)

            if self._retention_function is not None:
                logs = {
                    file
                    for pattern in self._glob_patterns
                    for file in glob.glob(pattern)
                    if os.path.isfile(file)
                }
                self._retention_function(list(logs))

        if is_rotating:
            self._create_file(new_path)
            set_ctime(new_path, datetime.datetime.now().timestamp())

    @staticmethod
    def _make_glob_patterns(path):
        formatter = string.Formatter()
        tokens = formatter.parse(path)
        escaped = "".join(glob.escape(text) + "*" * (name is not None) for text, name, *_ in tokens)

        root, ext = os.path.splitext(escaped)

        if not ext:
            return [escaped, escaped + ".*"]

        return [escaped, escaped + ".*", root + ".*" + ext, root + ".*" + ext + ".*"]

    @staticmethod
    def _make_rotation_function(rotation):
        if rotation is None:
            return None
        elif isinstance(rotation, str):
            size = string_parsers.parse_size(rotation)
            if size is not None:
                return FileSink._make_rotation_function(size)
            interval = string_parsers.parse_duration(rotation)
            if interval is not None:
                return FileSink._make_rotation_function(interval)
            frequency = string_parsers.parse_frequency(rotation)
            if frequency is not None:
                return Rotation.RotationTime(frequency)
            daytime = string_parsers.parse_daytime(rotation)
            if daytime is not None:
                day, time = daytime
                if day is None:
                    return FileSink._make_rotation_function(time)
                if time is None:
                    time = datetime.time(0, 0, 0)
                step_forward = partial(Rotation.forward_weekday, weekday=day)
                return Rotation.RotationTime(step_forward, time)
            raise ValueError("Cannot parse rotation from: '%s'" % rotation)
        elif isinstance(rotation, (numbers.Real, decimal.Decimal)):
            return partial(Rotation.rotation_size, size_limit=rotation)
        elif isinstance(rotation, datetime.time):
            return Rotation.RotationTime(Rotation.forward_day, rotation)
        elif isinstance(rotation, datetime.timedelta):
            step_forward = partial(Rotation.forward_interval, interval=rotation)
            return Rotation.RotationTime(step_forward)
        elif callable(rotation):
            return rotation
        else:
            raise TypeError(
                "Cannot infer rotation for objects of type: '%s'" % type(rotation).__name__
            )

    @staticmethod
    def _make_retention_function(retention):
        if retention is None:
            return None
        elif isinstance(retention, str):
            interval = string_parsers.parse_duration(retention)
            if interval is None:
                raise ValueError("Cannot parse retention from: '%s'" % retention)
            return FileSink._make_retention_function(interval)
        elif isinstance(retention, int):
            return partial(Retention.retention_count, number=retention)
        elif isinstance(retention, datetime.timedelta):
            return partial(Retention.retention_age, seconds=retention.total_seconds())
        elif callable(retention):
            return retention
        else:
            raise TypeError(
                "Cannot infer retention for objects of type: '%s'" % type(retention).__name__
            )

    @staticmethod
    def _make_compression_function(compression):
        if compression is None:
            return None
        elif isinstance(compression, str):
            ext = compression.strip().lstrip(".")

            if ext == "gz":
                import gzip

                compress = partial(Compression.copy_compress, opener=gzip.open, mode="wb")
            elif ext == "bz2":
                import bz2

                compress = partial(Compression.copy_compress, opener=bz2.open, mode="wb")

            elif ext == "xz":
                import lzma

                compress = partial(
                    Compression.copy_compress, opener=lzma.open, mode="wb", format=lzma.FORMAT_XZ
                )

            elif ext == "lzma":
                import lzma

                compress = partial(
                    Compression.copy_compress, opener=lzma.open, mode="wb", format=lzma.FORMAT_ALONE
                )
            elif ext == "tar":
                import tarfile

                compress = partial(Compression.add_compress, opener=tarfile.open, mode="w:")
            elif ext == "tar.gz":
                import gzip
                import tarfile

                compress = partial(Compression.add_compress, opener=tarfile.open, mode="w:gz")
            elif ext == "tar.bz2":
                import bz2
                import tarfile

                compress = partial(Compression.add_compress, opener=tarfile.open, mode="w:bz2")

            elif ext == "tar.xz":
                import lzma
                import tarfile

                compress = partial(Compression.add_compress, opener=tarfile.open, mode="w:xz")
            elif ext == "zip":
                import zipfile

                compress = partial(
                    Compression.write_compress,
                    opener=zipfile.ZipFile,
                    mode="w",
                    compression=zipfile.ZIP_DEFLATED,
                )
            else:
                raise ValueError("Invalid compression format: '%s'" % ext)

            return partial(Compression.compression, ext="." + ext, compress_function=compress)
        elif callable(compression):
            return compression
        else:
            raise TypeError(
                "Cannot infer compression for objects of type: '%s'" % type(compression).__name__
            )
