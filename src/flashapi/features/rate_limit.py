"""Rate limiting — in-memory sliding window per IP."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any


class RateLimiter:
    """Simple in-memory rate limiter (per-IP, sliding window)."""

    def __init__(self, limit: int = 100, window: int = 60):
        self._limit = limit
        self._window = window
        self._requests: dict[str, list[float]] = defaultdict(list)

    @property
    def limit(self) -> int:
        return self._limit

    @property
    def window(self) -> int:
        return self._window

    def check(self, key: str) -> tuple[bool, int, int]:
        """Check if request is allowed.

        Returns (allowed, remaining, reset_seconds).
        """
        now = time.time()
        window_start = now - self._window

        requests = self._requests[key]
        self._requests[key] = [t for t in requests if t > window_start]
        requests = self._requests[key]

        remaining = max(0, self._limit - len(requests))
        reset = int(self._window - (now - requests[0])) if requests else self._window

        if len(requests) >= self._limit:
            return False, 0, reset

        self._requests[key].append(now)
        remaining = max(0, self._limit - len(self._requests[key]))
        return True, remaining, reset
