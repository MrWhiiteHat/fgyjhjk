"""Human review queue for uncertain or disputed predictions."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock


@dataclass
class ReviewItem:
    """Queued feedback item for manual review."""

    review_id: str
    feedback_id: str
    prediction_id: str
    model_version: str
    tenant_id: str
    submitted_at: str
    status: str = "pending"
    notes: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


class HumanReviewQueue:
    """Tracks feedback requiring human adjudication."""

    def __init__(self) -> None:
        self._items: dict[str, ReviewItem] = {}
        self._lock = RLock()

    def enqueue(self, item: ReviewItem) -> ReviewItem:
        """Add review item to queue."""

        with self._lock:
            self._items[item.review_id] = item
            return item

    def update_status(self, review_id: str, status: str, notes: str = "") -> ReviewItem:
        """Update review state and optional notes."""

        with self._lock:
            if review_id not in self._items:
                raise KeyError(f"Unknown review item: {review_id}")
            item = self._items[review_id]
            updated = ReviewItem(
                review_id=item.review_id,
                feedback_id=item.feedback_id,
                prediction_id=item.prediction_id,
                model_version=item.model_version,
                tenant_id=item.tenant_id,
                submitted_at=item.submitted_at,
                status=str(status),
                notes=str(notes),
                metadata=dict(item.metadata),
            )
            self._items[review_id] = updated
            return updated

    def pending(self) -> list[ReviewItem]:
        """Return pending and in-review items."""

        with self._lock:
            return [item for item in self._items.values() if item.status in {"pending", "in_review"}]

    def list_all(self) -> list[ReviewItem]:
        """Return all review items."""

        with self._lock:
            return list(self._items.values())
