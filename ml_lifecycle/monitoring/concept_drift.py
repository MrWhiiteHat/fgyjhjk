"""Concept drift detection based on confidence and error-rate shifts."""

from __future__ import annotations

from ml_lifecycle.monitoring.metrics_store import InferenceRecord


def confidence_shift(reference: list[InferenceRecord], current: list[InferenceRecord]) -> float:
    """Compute absolute change in average prediction confidence."""

    if not reference or not current:
        return 0.0
    ref_mean = sum(item.confidence for item in reference) / len(reference)
    cur_mean = sum(item.confidence for item in current) / len(current)
    return abs(cur_mean - ref_mean)


def error_rate(records: list[InferenceRecord]) -> float | None:
    """Compute error rate when labels are available, otherwise return None."""

    labeled = [item for item in records if item.true_label is not None]
    if not labeled:
        return None
    errors = [1 for item in labeled if int(item.prediction) != int(item.true_label)]
    return len(errors) / len(labeled)


def error_rate_delta(reference: list[InferenceRecord], current: list[InferenceRecord]) -> float | None:
    """Compute absolute change in error rates between baseline and current windows."""

    ref_error = error_rate(reference)
    cur_error = error_rate(current)
    if ref_error is None or cur_error is None:
        return None
    return abs(cur_error - ref_error)


def evaluate_concept_drift(reference: list[InferenceRecord], current: list[InferenceRecord]) -> dict[str, float | None]:
    """Return concept drift indicators for confidence and error shifts."""

    shift = confidence_shift(reference, current)
    delta = error_rate_delta(reference, current)
    return {
        "confidence_shift": shift,
        "error_rate_delta": delta,
    }
