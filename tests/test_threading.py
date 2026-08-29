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
from plainlog.handlers import BaseHandler


class CountingHandler(BaseHandler):
    def __init__(self):
        self.count = 0
        self._lock = threading.Lock()

    def process(self, record):
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

    log.configure(handler=handler, level="DEBUG")

    stop = False
    threads = []

    def log_loop():
        while not stop:
            log.info("x")

    def configure_loop():
        while not stop:
            log.configure(handler=handler, level="DEBUG")

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
    core.configure(handler=CountingHandler(), level="DEBUG")
    core.close()
    assert not core.is_alive()

    start = time.monotonic()
    core.configure(handler=CountingHandler(), level="DEBUG")
    elapsed = time.monotonic() - start

    assert elapsed < 1.0


def test_close_idempotent():
    core = Core()
    core.configure(handler=CountingHandler(), level="DEBUG")
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
    from plainlog.handlers import BaseHandler

    class QHandler(BaseHandler):
        def process(self, record):
            q.put(record["msg"])
            return record

    logger.configure(handler=QHandler(), level="DEBUG")
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
