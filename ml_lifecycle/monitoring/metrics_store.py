"""Production metrics storage for inference-level monitoring records."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock


@dataclass
class InferenceRecord:
    """Inference event used for drift and performance monitoring."""

    request_id: str
    model_version: str
    timestamp: str
    features: dict[str, float]
    prediction: int
    confidence: float
    latency_ms: float
    true_label: int | None = None
    metadata: dict[str, str] = field(default_factory=dict)


class MetricsStore:
    """Thread-safe in-memory store for inference monitoring data."""

    def __init__(self) -> None:
        self._records: list[InferenceRecord] = []
        self._lock = RLock()

    def add_record(self, record: InferenceRecord) -> None:
        """Add an inference record."""

        with self._lock:
            self._records.append(record)

    def list_records(self, model_version: str | None = None) -> list[InferenceRecord]:
        """List records optionally filtered by model version."""

        with self._lock:
            if model_version is None:
                return list(self._records)
            target = str(model_version)
            return [record for record in self._records if record.model_version == target]

    def recent_records(self, limit: int, model_version: str | None = None) -> list[InferenceRecord]:
        """Get most recent records with optional model filter."""

        records = self.list_records(model_version=model_version)
        if limit <= 0:
            return []
        return records[-limit:]
