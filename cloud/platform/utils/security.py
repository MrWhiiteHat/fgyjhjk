"""Security helpers for signing and verification."""

from __future__ import annotations

import hashlib
import hmac


def hmac_sha256(secret: str, payload: str) -> str:
    """Compute HMAC-SHA256 hex digest."""

    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def constant_time_equal(a: str, b: str) -> bool:
    """Compare strings using constant-time semantics."""

    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
