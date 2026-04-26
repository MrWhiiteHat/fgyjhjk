"""Time helpers with UTC normalization."""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""

    return datetime.now(tz=timezone.utc)


def utc_now_iso() -> str:
    """Return current UTC datetime in ISO-8601 format."""

    return utc_now().isoformat()
