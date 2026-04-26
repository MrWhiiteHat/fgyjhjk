"""Background worker for async job queue processing."""

from __future__ import annotations

from threading import Event, Thread
from typing import Callable, Dict

from cloud.platform.jobs.models import Job
from cloud.platform.jobs.queue import AsyncJobQueue

JobHandler = Callable[[Job], dict]


class JobWorker:
    """Background worker that processes queued jobs using registered handlers."""

    def __init__(self, queue: AsyncJobQueue, handlers: Dict[str, JobHandler], poll_interval_seconds: float = 0.2) -> None:
        self._queue = queue
        self._handlers = dict(handlers)
        self._poll_interval_seconds = float(poll_interval_seconds)
        self._stop_event = Event()
        self._thread: Thread | None = None

    def start(self) -> None:
        """Start worker thread."""

        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = Thread(target=self._run, name="cloud-job-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop worker thread and wait for clean shutdown."""

        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def register_handler(self, job_type: str, handler: JobHandler) -> None:
        """Register runtime handler for a job type."""

        self._handlers[str(job_type).strip()] = handler

    def _run(self) -> None:
        while not self._stop_event.is_set():
            job = self._queue.next_job_for_worker(timeout_seconds=self._poll_interval_seconds)
            if job is None:
                continue

            try:
                handler = self._handlers.get(job.job_type)
                if handler is None:
                    raise RuntimeError(f"No handler registered for job type: {job.job_type}")
                result = handler(job)
                self._queue.mark_succeeded(job.job_id, result=result)
            except Exception as exc:  # noqa: BLE001
                self._queue.mark_failed(job.job_id, str(exc))
