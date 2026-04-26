"""Corrected label storage mapped to original predictions."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock


@dataclass
class CorrectedLabel:
    """Human-provided corrected label linked to prediction."""

    prediction_id: str
    corrected_label: int
    model_version: str
    updated_at: str
    source: str


class LabelStore:
    """Thread-safe store for corrected labels."""

    def __init__(self) -> None:
        self._labels: dict[str, CorrectedLabel] = {}
        self._lock = RLock()

    def upsert(self, label: CorrectedLabel) -> None:
        """Insert or update corrected label by prediction id."""

        with self._lock:
            self._labels[label.prediction_id] = label

    def get(self, prediction_id: str) -> CorrectedLabel | None:
        """Get corrected label by prediction id."""

        with self._lock:
            return self._labels.get(str(prediction_id))

    def list_all(self) -> list[CorrectedLabel]:
        """Return all corrected labels."""

        with self._lock:
            return list(self._labels.values())
