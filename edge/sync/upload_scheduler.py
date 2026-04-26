"""Upload scheduler with exponential backoff for offline queue synchronization."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Callable

from edge.sync.offline_queue import OfflineQueue
from edge.sync.sync_protocol import SyncEnvelope


@dataclass(frozen=True)
class SchedulerConfig:
    """Scheduler behavior controls."""

    interval_seconds: int = 30
    max_attempts: int = 5
    backoff_base_seconds: float = 1.5
    backoff_max_seconds: float = 60.0


class UploadScheduler:
    """Drives sync attempts with capped retry backoff."""

    def __init__(self, queue: OfflineQueue, config: SchedulerConfig | None = None) -> None:
        self.queue = queue
        self.config = config or SchedulerConfig()

    def _retry_delay(self, attempts: int) -> float:
        delay = min(
            self.config.backoff_max_seconds,
            self.config.backoff_base_seconds * (2 ** max(0, attempts - 1)),
        )
        jitter = random.uniform(0.0, delay * 0.15)
        return delay + jitter

    def run_once(self, upload_fn: Callable[[SyncEnvelope], bool]) -> dict[str, int]:
        """Process one queue pass and return summary counts."""
        processed = 0
        success = 0
        failed = 0
        conflict = 0

        for item in self.queue.pending_items():
            processed += 1
            if item.attempts >= self.config.max_attempts:
                self.queue.mark_conflict(item.payload.event_id, "max_attempts_exceeded")
                conflict += 1
                continue

            self.queue.mark_syncing(item.payload.event_id)
            try:
                ok = bool(upload_fn(item))
                if ok:
                    self.queue.mark_synced(item.payload.event_id)
                    success += 1
                else:
                    self.queue.mark_failed(item.payload.event_id, "upload_fn_returned_false")
                    failed += 1
                    time.sleep(self._retry_delay(item.attempts + 1))
            except Exception as exc:  # noqa: BLE001
                self.queue.mark_failed(item.payload.event_id, str(exc))
                failed += 1
                time.sleep(self._retry_delay(item.attempts + 1))

        return {
            "processed": processed,
            "success": success,
            "failed": failed,
            "conflict": conflict,
        }
