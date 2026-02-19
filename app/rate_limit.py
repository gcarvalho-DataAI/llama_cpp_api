from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    remaining: int
    retry_after_s: int


class SlidingWindowRateLimiter:
    def __init__(self, limit_per_minute: int) -> None:
        self.limit_per_minute = max(1, limit_per_minute)
        self.window_s = 60.0
        self._buckets: dict[str, deque[float]] = defaultdict(deque)

    def check(self, client_id: str) -> RateLimitDecision:
        now = time.monotonic()
        bucket = self._buckets[client_id]
        window_start = now - self.window_s

        while bucket and bucket[0] < window_start:
            bucket.popleft()

        if len(bucket) >= self.limit_per_minute:
            retry_after = max(1, int(self.window_s - (now - bucket[0])))
            return RateLimitDecision(False, 0, retry_after)

        bucket.append(now)
        remaining = self.limit_per_minute - len(bucket)
        return RateLimitDecision(True, remaining, 0)
