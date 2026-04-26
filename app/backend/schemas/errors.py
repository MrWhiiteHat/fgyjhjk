"""Error response schemas for consistent API failure payloads."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class ErrorDetail(BaseModel):
    """Single structured error item."""

    error_code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Standardized error response schema."""

    success: bool = False
    request_id: str
    timestamp: datetime = Field(default_factory=_now_utc)
    error_code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    data: Optional[Any] = None
    errors: list[ErrorDetail] = Field(default_factory=list)
