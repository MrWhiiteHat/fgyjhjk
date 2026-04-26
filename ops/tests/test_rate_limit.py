import pytest

from ops.security.rate_limit import (
    InMemoryRateLimiter,
    RateLimitExceededError,
    build_rate_limit_key,
    enforce_rate_limit,
    rate_limit_headers,
)


def test_rate_limiter_allows_then_blocks():
    limiter = InMemoryRateLimiter(limit_per_window=2, window_seconds=60, enabled=True)
    key = build_rate_limit_key(client_ip="127.0.0.1", endpoint="/predict")

    first = limiter.check(key)
    second = limiter.check(key)
    third = limiter.check(key)

    assert first.allowed is True
    assert second.allowed is True
    assert third.allowed is False
    assert third.retry_after > 0


def test_enforce_rate_limit_raises_structured_error():
    limiter = InMemoryRateLimiter(limit_per_window=1, window_seconds=60, enabled=True)

    enforce_rate_limit(limiter, client_ip="127.0.0.1", endpoint="/predict")

    with pytest.raises(RateLimitExceededError) as exc:
        enforce_rate_limit(limiter, client_ip="127.0.0.1", endpoint="/predict")

    payload = exc.value.to_dict()
    assert payload["error"] == "RATE_LIMIT_EXCEEDED"
    headers = rate_limit_headers(exc.value.decision)
    assert "Retry-After" in headers
