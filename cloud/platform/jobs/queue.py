"""Thread-safe async job queue with retry and DLQ support."""

from __future__ import annotations

import queue
from dataclasses import replace
from threading import RLock
from typing import Dict, List

from cloud.platform.jobs.models import Job, JobStatus
from cloud.platform.tenancy.guard import TenantGuard
from cloud.platform.utils.exceptions import NotFoundError, ValidationError
from cloud.platform.utils.ids import new_id
from cloud.platform.utils.time import utc_now_iso


class AsyncJobQueue:
    """In-memory asynchronous queue with tenant-aware access methods."""

    def __init__(self) -> None:
        self._queue: queue.Queue[str] = queue.Queue()
        self._jobs: Dict[str, Job] = {}
        self._dead_letter_jobs: Dict[str, Job] = {}
        self._lock = RLock()

    def enqueue(
        self,
        *,
        tenant_id: str,
        job_type: str,
        payload: dict,
        max_retries: int = 3,
    ) -> Job:
        """Create and enqueue a job."""

        if not str(tenant_id).strip():
            raise ValidationError("tenant_id is required")
        if not str(job_type).strip():
            raise ValidationError("job_type is required")

        job = Job(
            job_id=new_id("job"),
            tenant_id=str(tenant_id).strip(),
            job_type=str(job_type).strip(),
            payload=dict(payload or {}),
            max_retries=max(0, int(max_retries)),
        )
        with self._lock:
            self._jobs[job.job_id] = job
        self._queue.put(job.job_id)
        return job

    def next_job_for_worker(self, timeout_seconds: float = 0.2) -> Job | None:
        """Fetch next queued job and transition it to running."""

        try:
            job_id = self._queue.get(timeout=timeout_seconds)
        except queue.Empty:
            return None

        with self._lock:
            existing = self._jobs.get(job_id)
            if not existing:
                return None
            if existing.status != JobStatus.QUEUED:
                return None
            running = replace(
                existing,
                status=JobStatus.RUNNING,
                attempts=existing.attempts + 1,
                updated_at=utc_now_iso(),
                error_message=None,
            )
            self._jobs[job_id] = running
            return running

    def mark_succeeded(self, job_id: str, result: dict) -> Job:
        """Mark job as succeeded."""

        with self._lock:
            job = self._get_job_or_raise(job_id)
            updated = replace(job, status=JobStatus.SUCCEEDED, result=dict(result or {}), updated_at=utc_now_iso())
            self._jobs[job_id] = updated
            return updated

    def mark_failed(self, job_id: str, error_message: str) -> Job:
        """Mark job as failed and retry or route to dead letter."""

        with self._lock:
            job = self._get_job_or_raise(job_id)
            safe_error = str(error_message).strip() or "Unknown error"
            if job.attempts <= job.max_retries:
                queued = replace(
                    job,
                    status=JobStatus.QUEUED,
                    error_message=safe_error,
                    updated_at=utc_now_iso(),
                )
                self._jobs[job_id] = queued
                self._queue.put(job_id)
                return queued

            dead = replace(
                job,
                status=JobStatus.DEAD_LETTER,
                error_message=safe_error,
                updated_at=utc_now_iso(),
            )
            self._jobs[job_id] = dead
            self._dead_letter_jobs[job_id] = dead
            return dead

    def cancel_job(self, *, actor_tenant_id: str, job_id: str) -> Job:
        """Cancel queued/running job in same tenant."""

        with self._lock:
            job = self._get_job_or_raise(job_id)
            TenantGuard.assert_same_tenant(actor_tenant_id, job.tenant_id)
            updated = replace(job, status=JobStatus.CANCELLED, updated_at=utc_now_iso())
            self._jobs[job_id] = updated
            return updated

    def get_job(self, *, actor_tenant_id: str, job_id: str) -> Job:
        """Read job under tenant isolation checks."""

        with self._lock:
            job = self._get_job_or_raise(job_id)
            TenantGuard.assert_same_tenant(actor_tenant_id, job.tenant_id)
            return job

    def list_jobs(self, *, actor_tenant_id: str, tenant_id: str) -> List[Job]:
        """List jobs for tenant."""

        TenantGuard.assert_same_tenant(actor_tenant_id, tenant_id)
        with self._lock:
            return [job for job in self._jobs.values() if job.tenant_id == tenant_id]

    def list_dead_letter_jobs(self, *, actor_tenant_id: str, tenant_id: str) -> List[Job]:
        """List dead-letter jobs for tenant."""

        TenantGuard.assert_same_tenant(actor_tenant_id, tenant_id)
        with self._lock:
            return [job for job in self._dead_letter_jobs.values() if job.tenant_id == tenant_id]

    def _get_job_or_raise(self, job_id: str) -> Job:
        job = self._jobs.get(job_id)
        if not job:
            raise NotFoundError(f"Job not found: {job_id}")
        return job
