"""In-memory rate limiting with optional admin bypass and response headers."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass
from threading import RLock
from typing import Deque, Dict


@dataclass
class RateLimitDecision:
    """Rate-limit result payload."""

    allowed: bool
    limit: int
    remaining: int
    retry_after: int
    key: str


class RateLimitExceededError(Exception):
    """Structured exception for blocked requests due to quota limits."""

    def __init__(self, decision: RateLimitDecision) -> None:
        super().__init__("Rate limit exceeded")
        self.decision = decision

    def to_dict(self) -> Dict[str, object]:
        return {
            "error": "RATE_LIMIT_EXCEEDED",
            "message": "Too many requests",
            "limit": self.decision.limit,
            "remaining": self.decision.remaining,
            "retry_after": self.decision.retry_after,
            "key": self.decision.key,
        }


class InMemoryRateLimiter:
    """Sliding-window in-memory rate limiter.

    Limitation: state is process-local and resets on restart; it is not shared across replicas.
    """

    def __init__(self, limit_per_window: int = 120, window_seconds: int = 60, enabled: bool = True) -> None:
        self.limit_per_window = int(limit_per_window)
        self.window_seconds = int(window_seconds)
        self.enabled = bool(enabled)
        self._events: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = RLock()

    def _evict_old(self, bucket: Deque[float], now: float) -> None:
        cutoff = now - self.window_seconds
        while bucket and bucket[0] < cutoff:
            bucket.popleft()

    def check(self, key: str, is_admin_override: bool = False) -> RateLimitDecision:
        if not self.enabled or is_admin_override:
            return RateLimitDecision(allowed=True, limit=self.limit_per_window, remaining=self.limit_per_window, retry_after=0, key=key)

        now = time.time()
        with self._lock:
            bucket = self._events[key]
            self._evict_old(bucket, now)

            if len(bucket) >= self.limit_per_window:
                retry_after = int(max(1, self.window_seconds - (now - bucket[0])))
                return RateLimitDecision(
                    allowed=False,
                    limit=self.limit_per_window,
                    remaining=0,
                    retry_after=retry_after,
                    key=key,
                )

            bucket.append(now)
            remaining = max(0, self.limit_per_window - len(bucket))
            return RateLimitDecision(
                allowed=True,
                limit=self.limit_per_window,
                remaining=remaining,
                retry_after=0,
                key=key,
            )

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


def build_rate_limit_key(client_ip: str, api_key: str | None = None, endpoint: str | None = None) -> str:
    """Build stable key by API key if present, otherwise by client IP."""
    principal = api_key.strip() if api_key else client_ip.strip()
    endpoint_suffix = endpoint.strip() if endpoint else "global"
    return f"{principal}:{endpoint_suffix}"


def rate_limit_headers(decision: RateLimitDecision) -> Dict[str, str]:
    """Headers commonly used to communicate quota state."""
    headers = {
        "X-RateLimit-Limit": str(decision.limit),
        "X-RateLimit-Remaining": str(decision.remaining),
    }
    if decision.retry_after > 0:
        headers["Retry-After"] = str(decision.retry_after)
    return headers


def enforce_rate_limit(
    limiter: InMemoryRateLimiter,
    client_ip: str,
    endpoint: str,
    api_key: str | None = None,
    is_admin_override: bool = False,
) -> RateLimitDecision:
    """Apply quota check and raise structured error if blocked."""
    key = build_rate_limit_key(client_ip=client_ip, api_key=api_key, endpoint=endpoint)
    decision = limiter.check(key=key, is_admin_override=is_admin_override)
    if not decision.allowed:
        raise RateLimitExceededError(decision)
    return decision
