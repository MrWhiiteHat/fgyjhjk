"""Production performance aggregation and threshold checks."""

from __future__ import annotations

from ml_lifecycle.monitoring.metrics_store import InferenceRecord, MetricsStore


class PerformanceMonitor:
    """Calculates aggregate performance indicators from inference records."""

    def __init__(self, metrics_store: MetricsStore) -> None:
        self._store = metrics_store

    def summarize(self, records: list[InferenceRecord]) -> dict[str, float | int | None]:
        """Summarize latency, confidence, and labeled performance metrics."""

        if not records:
            return {
                "count": 0,
                "mean_latency_ms": None,
                "mean_confidence": None,
                "accuracy": None,
                "error_rate": None,
            }

        count = len(records)
        mean_latency = sum(item.latency_ms for item in records) / count
        mean_confidence = sum(item.confidence for item in records) / count

        labeled = [item for item in records if item.true_label is not None]
        if labeled:
            correct = sum(1 for item in labeled if int(item.prediction) == int(item.true_label))
            accuracy = correct / len(labeled)
            error_rate = 1.0 - accuracy
        else:
            accuracy = None
            error_rate = None

        return {
            "count": count,
            "mean_latency_ms": mean_latency,
            "mean_confidence": mean_confidence,
            "accuracy": accuracy,
            "error_rate": error_rate,
        }

    def compare_recent(
        self,
        *,
        baseline_window: int,
        current_window: int,
        model_version: str | None = None,
    ) -> dict[str, dict[str, float | int | None]]:
        """Compare baseline and current performance windows."""

        records = self._store.list_records(model_version=model_version)
        baseline = records[-(baseline_window + current_window) : -current_window] if len(records) > current_window else []
        current = records[-current_window:] if records else []

        baseline_summary = self.summarize(baseline)
        current_summary = self.summarize(current)

        return {
            "baseline": baseline_summary,
            "current": current_summary,
        }
