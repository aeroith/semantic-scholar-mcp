"""Cross-process rate limiter for Semantic Scholar API requests."""

from __future__ import annotations

import fcntl
import time
from pathlib import Path


class RateLimiter:
    """Serialize acquires across processes with a minimum interval."""

    def __init__(
        self,
        interval: float = 1.0,
        lock_path: str = "/tmp/.semantic-scholar-rate-lock",
    ) -> None:
        self._interval = interval
        self._lock_path = Path(lock_path)

    def acquire(self) -> float:
        """Block until the next rate-limit slot is available.

        Returns the total time in seconds spent waiting (lock + rate limit).
        """
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        start = time.time()

        with self._lock_path.open("a+", encoding="ascii") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                lock_file.seek(0)
                raw_timestamp = lock_file.read().strip()
                last_acquire = float(raw_timestamp) if raw_timestamp else 0.0

                wait_time = self._interval - (time.time() - last_acquire)
                if wait_time > 0:
                    time.sleep(wait_time)

                lock_file.seek(0)
                lock_file.truncate()
                lock_file.write(f"{time.time():.9f}")
                lock_file.flush()
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

        return time.time() - start
