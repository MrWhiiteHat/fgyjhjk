"""Feedback sanitizer that quarantines suspicious records before retraining."""

from __future__ import annotations

from dataclasses import dataclass, field

from security_hardening.poisoning.anomaly_filter import AnomalyFilter, AnomalyFilterResult
from security_hardening.poisoning.label_consistency import LabelConsistencyChecker, LabelConsistencyResult


@dataclass
class SanitizationReport:
    """Sanitization output with accepted and quarantined feedback partitions."""

    accepted_records: list[dict] = field(default_factory=list)
    quarantined_records: list[dict] = field(default_factory=list)
    reasons_by_feedback_id: dict[str, list[str]] = field(default_factory=dict)
    stats: dict[str, float] = field(default_factory=dict)


class FeedbackSanitizer:
    """Sanitizes feedback and blocks suspicious poisoning patterns."""

    def __init__(
        self,
        anomaly_filter: AnomalyFilter | None = None,
        consistency_checker: LabelConsistencyChecker | None = None,
    ) -> None:
        self._anomaly_filter = anomaly_filter or AnomalyFilter()
        self._consistency_checker = consistency_checker or LabelConsistencyChecker()

    def sanitize(self, *, feedback_records: list[dict], policy: dict) -> SanitizationReport:
        """Apply anomaly and consistency checks then quarantine suspicious records."""

        anomaly_cfg = dict(policy.get("anomaly_filter") or {})
        anomaly: AnomalyFilterResult = self._anomaly_filter.detect(
            feedback_records=feedback_records,
            burst_window_seconds=int(anomaly_cfg.get("burst_window_seconds", 120)),
            burst_threshold=int(anomaly_cfg.get("burst_threshold", 25)),
            low_quality_confidence_threshold=float(anomaly_cfg.get("low_quality_confidence_threshold", 0.35)),
        )

        consistency_cfg = dict(policy.get("label_consistency") or {})
        consistency: LabelConsistencyResult = self._consistency_checker.evaluate(
            feedback_records=feedback_records,
            inconsistency_threshold=float(consistency_cfg.get("inconsistency_threshold", 0.4)),
            improbable_flip_ratio_threshold=float(consistency_cfg.get("improbable_flip_ratio_threshold", 0.7)),
        )

        reasons = {key: list(value) for key, value in anomaly.reasons_by_feedback_id.items()}

        suspicious_prediction_ids = set(consistency.inconsistent_prediction_ids) | set(
            consistency.improbable_flip_prediction_ids
        )
        for record in feedback_records:
            feedback_id = str(record.get("feedback_id", "")).strip()
            prediction_id = str(record.get("prediction_id", "")).strip()
            if not feedback_id:
                continue
            if prediction_id in suspicious_prediction_ids:
                reasons.setdefault(feedback_id, []).append("label_consistency_violation")

        accepted: list[dict] = []
        quarantined: list[dict] = []
        for record in feedback_records:
            feedback_id = str(record.get("feedback_id", "")).strip()
            if not feedback_id:
                continue
            record_reasons = sorted(set(reasons.get(feedback_id, [])))
            enriched = {**record, "sanitizer_reasons": record_reasons}
            if record_reasons:
                quarantined.append(enriched)
            else:
                accepted.append(enriched)

        total = len(accepted) + len(quarantined)
        quarantine_rate = len(quarantined) / max(total, 1)

        return SanitizationReport(
            accepted_records=accepted,
            quarantined_records=quarantined,
            reasons_by_feedback_id={k: sorted(set(v)) for k, v in reasons.items()},
            stats={
                "total_records": float(total),
                "accepted_records": float(len(accepted)),
                "quarantined_records": float(len(quarantined)),
                "quarantine_rate": float(quarantine_rate),
                "anomaly_rate": float(anomaly.stats.get("anomaly_rate", 0.0)),
            },
        )
