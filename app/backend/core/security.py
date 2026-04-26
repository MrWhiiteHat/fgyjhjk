"""Security primitives: optional API key auth and in-memory rate limiting."""

from __future__ import annotations

import hmac
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque, Dict

from fastapi import Request

from app.backend.config import Settings, get_settings
from app.backend.core.exceptions import AuthError, RateLimitError


@dataclass
class RateLimitRecord:
    """Sliding-window request record for one key."""

    timestamps: Deque[float]


class InMemoryRateLimiter:
    """Simple in-memory per-key rate limiter using sliding window."""

    def __init__(self, per_minute: int) -> None:
        self.per_minute = int(per_minute)
        self.window_seconds = 60.0
        self._lock = threading.Lock()
        self._store: Dict[str, RateLimitRecord] = defaultdict(lambda: RateLimitRecord(timestamps=deque()))

    def check(self, key: str) -> None:
        """Raise RateLimitError if key exceeds configured request rate."""
        now = time.time()
        with self._lock:
            record = self._store[key]
            while record.timestamps and (now - record.timestamps[0]) > self.window_seconds:
                record.timestamps.popleft()

            if len(record.timestamps) >= self.per_minute:
                raise RateLimitError(
                    message="Rate limit exceeded",
                    details={"limit_per_minute": self.per_minute},
                )

            record.timestamps.append(now)

    def clear(self) -> None:
        """Clear all rate limit state."""
        with self._lock:
            self._store.clear()


_RATE_LIMITER: InMemoryRateLimiter | None = None
_RATE_LIMITER_LOCK = threading.Lock()


def get_rate_limiter(settings: Settings | None = None) -> InMemoryRateLimiter:
    """Return process-wide in-memory rate limiter instance."""
    global _RATE_LIMITER
    cfg = settings or get_settings()
    with _RATE_LIMITER_LOCK:
        if _RATE_LIMITER is None or _RATE_LIMITER.per_minute != int(cfg.RATE_LIMIT_PER_MINUTE):
            _RATE_LIMITER = InMemoryRateLimiter(per_minute=int(cfg.RATE_LIMIT_PER_MINUTE))
    return _RATE_LIMITER


def authenticate_api_key(request: Request, settings: Settings | None = None) -> None:
    """Enforce optional API key auth using constant-time comparison."""
    cfg = settings or get_settings()
    if not bool(cfg.ENABLE_AUTH):
        return

    supplied = request.headers.get("X-API-Key", "")
    expected = str(cfg.API_KEY)
    if not supplied or not expected:
        raise AuthError("API key is required")

    if not hmac.compare_digest(supplied, expected):
        raise AuthError("Invalid API key")


def apply_rate_limit(request: Request, settings: Settings | None = None) -> None:
    """Apply optional per-client rate limiting."""
    cfg = settings or get_settings()
    if not bool(cfg.ENABLE_RATE_LIMIT):
        return

    client_host = request.client.host if request.client else "unknown-client"
    key = f"{client_host}:{request.url.path}"
    limiter = get_rate_limiter(cfg)
    limiter.check(key)
