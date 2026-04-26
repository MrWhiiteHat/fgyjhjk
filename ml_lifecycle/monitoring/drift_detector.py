"""Unified drift detector orchestrating data and concept drift checks."""

from __future__ import annotations

from ml_lifecycle.monitoring.alert_rules import Alert, AlertRules
from ml_lifecycle.monitoring.concept_drift import evaluate_concept_drift
from ml_lifecycle.monitoring.data_drift import aggregate_data_drift, compare_feature_distributions
from ml_lifecycle.monitoring.metrics_store import InferenceRecord


class DriftDetector:
    """Computes drift signals and returns alertable monitoring reports."""

    def __init__(self, alert_rules: AlertRules | None = None) -> None:
        self._alert_rules = alert_rules or AlertRules()

    def detect(self, *, reference: list[InferenceRecord], current: list[InferenceRecord], bins: int = 10) -> dict:
        """Run full drift detection and produce scores and alerts."""

        if not reference or not current:
            return {
                "data_drift": {"feature_scores": {}, "aggregate_score": 0.0},
                "concept_drift": {"confidence_shift": 0.0, "error_rate_delta": None},
                "alerts": [],
            }

        ref_features = [item.features for item in reference]
        cur_features = [item.features for item in current]

        feature_scores = compare_feature_distributions(ref_features, cur_features, bins=bins)
        aggregate_score = aggregate_data_drift(feature_scores)

        concept = evaluate_concept_drift(reference, current)
        confidence_shift = float(concept["confidence_shift"] or 0.0)
        error_rate_delta = concept["error_rate_delta"]

        alerts: list[Alert] = self._alert_rules.evaluate_drift(
            data_drift_score=aggregate_score,
            confidence_shift=confidence_shift,
            error_rate_delta=error_rate_delta,
        )

        return {
            "data_drift": {
                "feature_scores": feature_scores,
                "aggregate_score": aggregate_score,
            },
            "concept_drift": concept,
            "alerts": alerts,
        }
