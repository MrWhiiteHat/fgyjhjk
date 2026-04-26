"""Common response schema primitives for API contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.backend.schemas.errors import ErrorDetail


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class BaseResponse(BaseModel):
    """Base API response wrapper shared by success and failure payloads."""

    success: bool = True
    request_id: str
    timestamp: datetime = Field(default_factory=_now_utc)
    message: str = ""
    data: Optional[Any] = None
    errors: list[ErrorDetail] = Field(default_factory=list)
