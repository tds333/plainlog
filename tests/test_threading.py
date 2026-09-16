# SPDX-FileCopyrightText: 2023 Wolfgang Langner <tds333@mailbox.org>
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
import multiprocessing as mp
import os
import threading
import time
import warnings

import pytest

from plainlog._logger import Core, Logger, _reset_for_fork, logger_core


class CountingHandler:
    def __init__(self):
        self.count = 0
        self._lock = threading.Lock()

    def __call__(self, record):
        with self._lock:
            self.count += 1
        return record


def _fork_available():
    try:
        mp.get_context("fork")
        return True
    except ValueError:
        return False


def test_concurrent_reconfigure_and_log():
    core = Core()
    handler = CountingHandler()
    log = Logger(core=core, name="root", extra={})

    log.configure(processors=[handler], level="DEBUG")

    stop = False
    threads = []

    def log_loop():
        while not stop:
            log.info("x")

    def configure_loop():
        while not stop:
            log.configure(processors=[handler], level="DEBUG")

    for _ in range(4):
        threads.append(threading.Thread(target=log_loop))
    for _ in range(2):
        threads.append(threading.Thread(target=configure_loop))

    for t in threads:
        t.start()
    time.sleep(0.3)
    stop = True
    for t in threads:
        t.join()

    core.close()

    assert handler.count > 0


def test_close_then_configure_no_hang():
    core = Core()
    core.configure(processors=[CountingHandler()], level="DEBUG")
    core.close()
    assert not core.is_alive()

    start = time.monotonic()
    core.configure(processors=[CountingHandler()], level="DEBUG")
    elapsed = time.monotonic() - start

    assert elapsed < 1.0


def test_close_idempotent():
    core = Core()
    core.configure(processors=[CountingHandler()], level="DEBUG")
    core.close()
    core.close()

    assert not core.is_alive()


def test_wait_for_processed_dead_core():
    core = Core()
    core.close()
    # Must return immediately on a dead worker, not block on an Event
    # the worker will never set.
    core.wait_for_processed()
    assert not core.is_alive()


def test_register_fork_hook_skipped_without_register_at_fork(monkeypatch):
    import plainlog._logger as mod

    monkeypatch.delattr(os, "register_at_fork", raising=False)
    # Should not raise and should skip registration (false branch).
    mod._register_fork_hook()


def test_worker_ignores_processor_returning_non_dict():
    class Poison:
        def __call__(self, record):
            return "poisoned"

    captured = []

    class Recorder:
        def __call__(self, record):
            captured.append(record)
            return record

    core = Core()
    log = Logger(core=core, name="t")
    core.configure(processors=[Poison(), Recorder()], level="DEBUG")

    log.info("one message")
    core.wait_for_processed(2)
    assert core.is_alive()
    assert captured, "downstream processor never ran"
    record = captured[0]
    assert isinstance(record, dict)
    assert record["msg"] == "one message"
    assert "processor_error_message" not in record
    assert "processor_error_name_repr" not in record

    log.info("second message")
    core.wait_for_processed(2)
    assert core.is_alive()
    assert len(captured) == 2
    assert captured[1]["msg"] == "second message"

    core.stop()
    core.join()


def test_worker_survives_poisoned_record_and_processor_exception():
    class Poison:
        def __call__(self, record):
            return "poisoned"

    class Raising:
        def __call__(self, record):
            raise ValueError("boom")

    captured = []

    class Recorder:
        def __call__(self, record):
            captured.append(record)
            return record

    core = Core()
    log = Logger(core=core, name="t")
    core.configure(processors=[Poison(), Raising(), Recorder()], level="DEBUG")

    log.info("one message")
    core.wait_for_processed(2)
    assert core.is_alive()
    assert captured, "downstream processor never ran"
    record = captured[0]
    assert isinstance(record, dict)
    assert record["processor_error_message"] == "boom"
    assert "Raising" in record["processor_error_name_repr"]

    core.stop()
    core.join()


def test_worker_survives_processor_exception():
    captured = []

    class Recorder:
        def __call__(self, record):
            captured.append(record)
            return record

    class Raising:
        def __call__(self, record):
            raise ValueError("boom")

    core = Core()
    log = Logger(core=core, name="t")
    core.configure(processors=[Raising(), Recorder()], level="DEBUG")

    log.info("first message")
    core.wait_for_processed(2)
    assert core.is_alive()
    assert captured
    assert captured[0]["processor_error_message"] == "boom"

    core.stop()
    core.join()


def test_worker_survives_hostile_repr():
    class Hostile:
        def __call__(self, record):
            raise ValueError("boom")

        def __repr__(self):
            raise RuntimeError("bad repr")

    captured = []

    class Recorder:
        def __call__(self, record):
            captured.append(record)
            return record

    core = Core()
    log = Logger(core=core, name="t")
    core.configure(processors=[Hostile(), Recorder()], level="DEBUG")

    log.info("one message")
    core.wait_for_processed(2)

    assert core.is_alive()
    assert captured
    record = captured[0]
    assert record["processor_error_message"] == "boom"
    assert record["processor_error_name_repr"] == "<unprintable>"

    core.stop()
    core.join()


def test_worker_survives_hostile_str_exception():
    class BadStrError(Exception):
        def __str__(self):
            raise RuntimeError("bad str")

    class Raising:
        def __call__(self, record):
            raise BadStrError()

    captured = []

    class Recorder:
        def __call__(self, record):
            captured.append(record)
            return record

    core = Core()
    log = Logger(core=core, name="t")
    core.configure(processors=[Raising(), Recorder()], level="DEBUG")

    log.info("one message")
    core.wait_for_processed(2)

    assert core.is_alive()
    assert captured
    assert captured[0]["processor_error_message"] == "<unprintable>"

    core.stop()
    core.join()


def test_configure_from_processor_does_not_stall():
    core = Core()
    log = Logger(core=core, name="t")

    calls = []

    class Reentrant:
        def __call__(self, record):
            if not calls:
                calls.append(True)
                log.configure(processors=[Reentrant()], level="DEBUG")
            return record

    core.configure(processors=[Reentrant()], level="DEBUG")

    start = time.monotonic()
    log.info("trigger")
    core.wait_for_processed(10)
    elapsed = time.monotonic() - start

    assert core.is_alive()
    assert elapsed < 2.0

    core.stop()
    core.join()


def test_wait_for_processed_is_bounded(monkeypatch):
    import plainlog._logger as mod

    core = Core()
    # stop the real worker so nothing consumes the EVENT command
    core.stop()
    core.join()

    class FakeThread:
        def is_alive(self):
            return True

        def join(self):
            pass

    core._thread = FakeThread()
    monkeypatch.setattr(mod._env, "DEFAULT_WAIT_TIMEOUT", 0.05)

    start = time.monotonic()
    worker = threading.Thread(target=core.wait_for_processed, daemon=True)
    worker.start()
    worker.join(2.0)
    elapsed = time.monotonic() - start

    assert not worker.is_alive(), "wait_for_processed did not return"
    assert elapsed < 1.0


def test_reset_for_fork_restarts_worker():
    old_thread = logger_core._thread
    old_queue = logger_core._queue

    _reset_for_fork()

    try:
        assert logger_core._thread is not old_thread
        assert logger_core._thread.is_alive()
        assert logger_core._queue is not old_queue
    finally:
        logger_core.stop()
        logger_core.join()
        logger_core._thread = old_thread
        logger_core._queue = old_queue

    assert old_thread.is_alive()


def _child_log(q):
    from plainlog import logger

    class QHandler:
        def __call__(self, record):
            q.put(record["msg"])
            return record

    logger.configure(processors=[QHandler()], level="DEBUG")
    logger.info("child-message")
    logger_core.wait_for_processed()


@pytest.mark.skipif(
    not _fork_available(),
    reason="fork start method not available on this platform",
)
def test_fork_reset_logs_in_child():
    ctx = mp.get_context("fork")
    q = ctx.Queue()
    p = ctx.Process(target=_child_log, args=(q,))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        p.start()
    p.join(timeout=10)

    assert p.exitcode == 0
    assert q.get(timeout=5) == "child-message"
