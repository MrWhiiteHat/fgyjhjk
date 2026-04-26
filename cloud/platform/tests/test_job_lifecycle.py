"""Async job lifecycle tests including retry and dead-letter transitions."""

from __future__ import annotations

import time

from cloud.platform.jobs.models import Job, JobStatus
from cloud.platform.jobs.queue import AsyncJobQueue
from cloud.platform.jobs.worker import JobWorker


def _wait_for_terminal_status(queue: AsyncJobQueue, tenant_id: str, job_id: str, timeout_seconds: float = 3.0) -> Job:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        job = queue.get_job(actor_tenant_id=tenant_id, job_id=job_id)
        if job.status in {JobStatus.SUCCEEDED, JobStatus.DEAD_LETTER, JobStatus.CANCELLED}:
            return job
        time.sleep(0.05)
    return queue.get_job(actor_tenant_id=tenant_id, job_id=job_id)


def test_job_succeeds_after_retry() -> None:
    attempts: dict[str, int] = {}

    def flaky_handler(job: Job) -> dict:
        count = attempts.get(job.job_id, 0) + 1
        attempts[job.job_id] = count
        if count == 1:
            raise RuntimeError("transient")
        return {"ok": True, "attempt": count}

    queue = AsyncJobQueue()
    worker = JobWorker(queue=queue, handlers={"inference": flaky_handler}, poll_interval_seconds=0.05)
    worker.start()

    tenant_id = "tenant-job-a"
    job = queue.enqueue(tenant_id=tenant_id, job_type="inference", payload={"x": 1}, max_retries=2)
    final = _wait_for_terminal_status(queue, tenant_id=tenant_id, job_id=job.job_id)

    worker.stop()

    assert final.status == JobStatus.SUCCEEDED
    assert final.attempts >= 2
    assert final.result is not None
    assert final.result["ok"] is True


def test_job_moves_to_dead_letter_after_exhausted_retries() -> None:
    def always_fail(_job: Job) -> dict:
        raise RuntimeError("always failing")

    queue = AsyncJobQueue()
    worker = JobWorker(queue=queue, handlers={"batch": always_fail}, poll_interval_seconds=0.05)
    worker.start()

    tenant_id = "tenant-job-b"
    job = queue.enqueue(tenant_id=tenant_id, job_type="batch", payload={"x": 2}, max_retries=1)
    final = _wait_for_terminal_status(queue, tenant_id=tenant_id, job_id=job.job_id)

    worker.stop()

    assert final.status == JobStatus.DEAD_LETTER
    dlq = queue.list_dead_letter_jobs(actor_tenant_id=tenant_id, tenant_id=tenant_id)
    assert any(item.job_id == job.job_id for item in dlq)
