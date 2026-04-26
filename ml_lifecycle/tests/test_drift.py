"""Drift detection simulation tests."""

from __future__ import annotations

from ml_lifecycle.monitoring.alert_rules import AlertRules
from ml_lifecycle.monitoring.drift_detector import DriftDetector
from ml_lifecycle.monitoring.metrics_store import InferenceRecord


def _record(idx: int, x: float, confidence: float, prediction: int, label: int | None) -> InferenceRecord:
    return InferenceRecord(
        request_id=f"r_{idx}",
        model_version="1.0.0",
        timestamp="2026-04-18T00:00:00+00:00",
        features={"x": x, "y": x * 0.5},
        prediction=prediction,
        confidence=confidence,
        latency_ms=20.0,
        true_label=label,
    )


def test_data_and_concept_drift_alerts_triggered() -> None:
    reference = [_record(i, x=0.1 + (i % 3) * 0.02, confidence=0.92, prediction=0, label=0) for i in range(120)]
    current = [_record(i + 200, x=1.4 + (i % 3) * 0.05, confidence=0.55, prediction=1, label=0) for i in range(120)]

    detector = DriftDetector(
        alert_rules=AlertRules(
            data_drift_threshold=0.05,
            confidence_shift_threshold=0.05,
            error_rate_delta_threshold=0.02,
        )
    )
    report = detector.detect(reference=reference, current=current)

    assert report["data_drift"]["aggregate_score"] >= 0.05
    assert report["concept_drift"]["confidence_shift"] >= 0.05
    assert report["concept_drift"]["error_rate_delta"] is not None
    assert len(report["alerts"]) >= 1
