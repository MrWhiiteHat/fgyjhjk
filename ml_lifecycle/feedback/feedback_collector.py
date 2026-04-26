"""Feedback collector linking user feedback to prediction outcomes."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock

from ml_lifecycle.feedback.human_review_queue import HumanReviewQueue, ReviewItem
from ml_lifecycle.feedback.label_store import CorrectedLabel, LabelStore


@dataclass
class FeedbackRecord:
    """Feedback record mapped to original model prediction."""

    feedback_id: str
    prediction_id: str
    model_version: str
    tenant_id: str
    submitted_at: str
    corrected_label: int | None = None
    confidence: float | None = None
    comment: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


class FeedbackCollector:
    """Captures user feedback and routes uncertain cases for review."""

    def __init__(self, review_queue: HumanReviewQueue | None = None, label_store: LabelStore | None = None) -> None:
        self._review_queue = review_queue or HumanReviewQueue()
        self._label_store = label_store or LabelStore()
        self._records: dict[str, FeedbackRecord] = {}
        self._lock = RLock()

    def capture_feedback(self, record: FeedbackRecord) -> FeedbackRecord:
        """Store feedback, save corrected label, and optionally enqueue review."""

        with self._lock:
            self._records[record.feedback_id] = record

        if record.corrected_label is not None:
            self._label_store.upsert(
                CorrectedLabel(
                    prediction_id=record.prediction_id,
                    corrected_label=int(record.corrected_label),
                    model_version=record.model_version,
                    updated_at=record.submitted_at,
                    source="feedback",
                )
            )

        if record.corrected_label is None or (record.confidence is not None and float(record.confidence) < 0.5):
            self._review_queue.enqueue(
                ReviewItem(
                    review_id=f"review_{record.feedback_id}",
                    feedback_id=record.feedback_id,
                    prediction_id=record.prediction_id,
                    model_version=record.model_version,
                    tenant_id=record.tenant_id,
                    submitted_at=record.submitted_at,
                    metadata={"reason": "no_label_or_low_confidence"},
                )
            )

        return record

    def list_feedback(self, tenant_id: str | None = None) -> list[FeedbackRecord]:
        """List feedback records optionally filtered by tenant."""

        with self._lock:
            records = list(self._records.values())
        if tenant_id is None:
            return records
        safe_tenant = str(tenant_id)
        return [record for record in records if record.tenant_id == safe_tenant]

    def map_feedback_to_prediction(self, prediction_id: str) -> list[FeedbackRecord]:
        """Find all feedback records linked to a prediction id."""

        target = str(prediction_id)
        with self._lock:
            return [record for record in self._records.values() if record.prediction_id == target]

    @property
    def review_queue(self) -> HumanReviewQueue:
        """Expose review queue integration."""

        return self._review_queue

    @property
    def label_store(self) -> LabelStore:
        """Expose corrected label store integration."""

        return self._label_store
