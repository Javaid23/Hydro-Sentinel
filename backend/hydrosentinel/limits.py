"""
Bounds on work a caller can ask for.

Two endpoints do real work on demand: a live extraction reads 13 rasters, and building a location
baseline reads up to 48 scenes over several minutes. Both are reachable with arbitrary coordinates,
so without limits a single client can saturate the process, fill the disk with cache entries, or
run up bandwidth on a free-tier host during judging.

Deliberately dependency-free and in-process: one instance serves this API, so a shared store would
add operational weight for no benefit. If it were ever run multi-worker, these become per-worker
limits — which is noted rather than hidden.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque

log = logging.getLogger(__name__)


class RateLimited(Exception):
    """Raised when a caller exceeds the allowance for an expensive operation."""

    def __init__(self, retry_after: int, message: str):
        super().__init__(message)
        self.retry_after = retry_after


class RateLimiter:
    """Sliding-window limit per caller, plus a cap on concurrent expensive operations.

    The concurrency cap matters as much as the rate: several baseline builds at once would each
    hold a thread pool open against the imagery archive.
    """

    def __init__(self, max_calls: int, window_seconds: float, max_concurrent: int, name: str = "operation"):
        self.max_calls = max_calls
        self.window = window_seconds
        self.name = name
        self._calls: dict[str, deque[float]] = {}
        self._lock = threading.Lock()
        self._slots = threading.BoundedSemaphore(max_concurrent)
        self.max_concurrent = max_concurrent

    def check(self, caller: str) -> None:
        """Record a call from `caller`, or raise RateLimited."""
        now = time.monotonic()
        with self._lock:
            hits = self._calls.setdefault(caller, deque())
            while hits and now - hits[0] > self.window:
                hits.popleft()
            if len(hits) >= self.max_calls:
                retry = int(self.window - (now - hits[0])) + 1
                raise RateLimited(retry, f"too many {self.name} requests; retry in {retry}s")
            hits.append(now)
            # keep the caller table from growing without bound
            if len(self._calls) > 1024:
                for key in [k for k, v in self._calls.items() if not v or now - v[-1] > self.window]:
                    self._calls.pop(key, None)

    def acquire(self, timeout: float = 0.0) -> bool:
        """Take a concurrency slot. Returns False if none is free."""
        return self._slots.acquire(blocking=timeout > 0, timeout=timeout or None)

    def release(self) -> None:
        try:
            self._slots.release()
        except ValueError:  # pragma: no cover - released more than acquired
            pass


class _Slot:
    """Context manager wrapping acquire/release so a failure cannot leak a slot."""

    def __init__(self, limiter: RateLimiter, timeout: float):
        self.limiter, self.timeout, self.got = limiter, timeout, False

    def __enter__(self) -> bool:
        self.got = self.limiter.acquire(self.timeout)
        return self.got

    def __exit__(self, *exc) -> None:
        if self.got:
            self.limiter.release()


def slot(limiter: RateLimiter, timeout: float = 0.0) -> _Slot:
    return _Slot(limiter, timeout)


# A live extraction is ~13 range reads; a baseline is up to 48 of those. The baseline allowance is
# deliberately tight: it is minutes of work per call.
LIVE = RateLimiter(max_calls=20, window_seconds=60, max_concurrent=3, name="live extraction")
BASELINE = RateLimiter(max_calls=3, window_seconds=600, max_concurrent=1, name="baseline build")
