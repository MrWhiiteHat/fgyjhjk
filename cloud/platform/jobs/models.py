"""Job domain models for async processing."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict

from cloud.platform.utils.time import utc_now_iso


class JobStatus(str, Enum):
    """Lifecycle states for async jobs."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"
    CANCELLED = "cancelled"


@dataclass
class Job:
    """Asynchronous tenant-scoped job."""

    job_id: str
    tenant_id: str
    job_type: str
    payload: Dict[str, Any]
    status: JobStatus = JobStatus.QUEUED
    attempts: int = 0
    max_retries: int = 3
    result: Dict[str, Any] | None = None
    error_message: str | None = None
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
