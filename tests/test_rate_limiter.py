"""Tests for cross-process FIFO rate limiter."""

import multiprocessing
import os
import tempfile
import time

import pytest

from semantic_scholar_mcp.rate_limiter import RateLimiter


@pytest.fixture
def lock_path(tmp_path):
    return str(tmp_path / "rate-lock")


class TestRateLimiter:
    def test_creates_lock_file_on_first_acquire(self, lock_path: str):
        limiter = RateLimiter(interval=1.0, lock_path=lock_path)
        limiter.acquire()
        assert os.path.exists(lock_path)

    def test_first_acquire_returns_immediately(self, lock_path: str):
        limiter = RateLimiter(interval=1.0, lock_path=lock_path)
        start = time.monotonic()
        limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed < 0.1

    def test_second_acquire_waits_full_interval(self, lock_path: str):
        limiter = RateLimiter(interval=1.0, lock_path=lock_path)
        limiter.acquire()
        start = time.monotonic()
        limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed >= 0.9

    def test_respects_custom_interval(self, lock_path: str):
        limiter = RateLimiter(interval=0.3, lock_path=lock_path)
        limiter.acquire()
        start = time.monotonic()
        limiter.acquire()
        elapsed = time.monotonic() - start
        assert 0.2 <= elapsed < 0.5

    def test_no_wait_after_interval_elapses(self, lock_path: str):
        limiter = RateLimiter(interval=0.2, lock_path=lock_path)
        limiter.acquire()
        time.sleep(0.3)
        start = time.monotonic()
        limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed < 0.1


class TestRateLimiterCrossProcess:
    """Verify the limiter coordinates across independent OS processes."""

    def test_cross_process_serialization(self, lock_path: str):
        """Three processes each acquire once; wall-clock >= 2*interval."""

        def worker(lock_path: str, interval: float, result_queue):
            limiter = RateLimiter(interval=interval, lock_path=lock_path)
            limiter.acquire()
            result_queue.put(time.time())

        interval = 0.5
        q: multiprocessing.Queue = multiprocessing.Queue()
        procs = []
        for _ in range(3):
            p = multiprocessing.Process(target=worker, args=(lock_path, interval, q))
            procs.append(p)

        start = time.time()
        for p in procs:
            p.start()
        for p in procs:
            p.join(timeout=10)

        timestamps = sorted([q.get() for _ in range(3)])
        total_span = timestamps[-1] - timestamps[0]
        # 3 acquires → 2 gaps of at least `interval` each
        assert total_span >= interval * 1.8  # small tolerance

    def test_fifo_ordering(self, lock_path: str):
        """Processes that block on the lock are served roughly in arrival order."""

        def worker(lock_path: str, interval: float, worker_id: int, result_queue):
            limiter = RateLimiter(interval=interval, lock_path=lock_path)
            limiter.acquire()
            result_queue.put((worker_id, time.time()))

        interval = 0.3
        q: multiprocessing.Queue = multiprocessing.Queue()

        # First acquire to "prime" the lock so subsequent ones must wait.
        limiter = RateLimiter(interval=interval, lock_path=lock_path)
        limiter.acquire()

        procs = []
        for i in range(3):
            p = multiprocessing.Process(target=worker, args=(lock_path, interval, i, q))
            procs.append(p)

        # Start them in order with tiny stagger so arrival order is deterministic.
        for p in procs:
            p.start()
            time.sleep(0.02)

        for p in procs:
            p.join(timeout=10)

        results = sorted([q.get() for _ in range(3)], key=lambda x: x[1])
        served_order = [r[0] for r in results]
        assert served_order == [0, 1, 2]
