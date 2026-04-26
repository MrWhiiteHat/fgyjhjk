"""Queue guard for bounding pending requests and staleness under load."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, Generic, Optional, TypeVar


T = TypeVar("T")


@dataclass
class QueueItem(Generic[T]):
    """Queue item wrapper with enqueue timestamp."""

    value: T
    enqueued_at: float


class QueueGuard(Generic[T]):
    """Bounded queue with configurable overflow behavior."""

    def __init__(
        self,
        max_queue_size: int = 256,
        max_wait_seconds: float = 10.0,
        overflow_policy: str = "reject_new",  # reject_new | drop_oldest
    ) -> None:
        self.max_queue_size = int(max_queue_size)
        self.max_wait_seconds = float(max_wait_seconds)
        self.overflow_policy = str(overflow_policy)
        self._queue: Deque[QueueItem[T]] = deque()
        self._dropped_count = 0

    def _evict_stale(self) -> int:
        now = time.time()
        removed = 0
        while self._queue and (now - self._queue[0].enqueued_at) > self.max_wait_seconds:
            self._queue.popleft()
            removed += 1
            self._dropped_count += 1
        return removed

    def enqueue(self, value: T) -> bool:
        self._evict_stale()
        if len(self._queue) >= self.max_queue_size:
            if self.overflow_policy == "drop_oldest":
                self._queue.popleft()
                self._dropped_count += 1
            else:
                self._dropped_count += 1
                return False
        self._queue.append(QueueItem(value=value, enqueued_at=time.time()))
        return True

    def dequeue(self) -> Optional[T]:
        self._evict_stale()
        if not self._queue:
            return None
        return self._queue.popleft().value

    def size(self) -> int:
        self._evict_stale()
        return len(self._queue)

    def status(self) -> Dict[str, object]:
        self._evict_stale()
        oldest_age = 0.0
        if self._queue:
            oldest_age = max(0.0, time.time() - self._queue[0].enqueued_at)
        return {
            "queue_size": len(self._queue),
            "max_queue_size": self.max_queue_size,
            "max_wait_seconds": self.max_wait_seconds,
            "overflow_policy": self.overflow_policy,
            "oldest_item_age_seconds": round(oldest_age, 6),
            "dropped_count": self._dropped_count,
        }
