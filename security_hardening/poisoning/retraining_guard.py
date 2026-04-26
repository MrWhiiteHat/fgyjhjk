"""Retraining guard to block insecure training batches."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RetrainingGuardReport:
    """Approval or rejection report for candidate retraining batch."""

    approved: bool
    reasons: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)
    module9_integration: dict[str, object] = field(default_factory=dict)


class RetrainingGuard:
    """Validates poisoning and data quality constraints before retraining inclusion."""

    def evaluate_batch(
        self,
        *,
        candidate_samples: list[dict],
        sanitization_report: dict,
        policy: dict,
        module9_trigger_context: dict | None = None,
    ) -> RetrainingGuardReport:
        """Approve or reject batch based on suspiciousness, skew, and provenance."""

        reasons: list[str] = []

        thresholds = dict(policy.get("retraining_guard") or {})
        max_suspicious_ratio = float(thresholds.get("max_suspicious_feedback_ratio", 0.3))
        max_class_skew = float(thresholds.get("max_class_skew", 0.75))
        max_anomaly_rate = float(thresholds.get("max_anomaly_rate", 0.25))
        max_missing_provenance_rate = float(thresholds.get("max_missing_provenance_rate", 0.1))

        stats = dict(sanitization_report.get("stats") or {})
        suspicious_ratio = float(stats.get("quarantine_rate", 0.0))
        anomaly_rate = float(stats.get("anomaly_rate", 0.0))

        labels = [int(sample.get("label")) for sample in candidate_samples if sample.get("label") in {0, 1}]
        if labels:
            positives = sum(1 for label in labels if label == 1)
            negatives = len(labels) - positives
            dominant_ratio = max(positives, negatives) / len(labels)
        else:
            dominant_ratio = 1.0
            reasons.append("missing_labels")

        provenance_missing = sum(1 for sample in candidate_samples if not sample.get("provenance"))
        missing_provenance_rate = provenance_missing / max(len(candidate_samples), 1)

        if suspicious_ratio > max_suspicious_ratio:
            reasons.append("too_much_suspicious_feedback")
        if dominant_ratio > max_class_skew:
            reasons.append("class_skew_too_extreme")
        if anomaly_rate > max_anomaly_rate:
            reasons.append("anomaly_rate_too_high")
        if missing_provenance_rate > max_missing_provenance_rate:
            reasons.append("data_provenance_missing")

        approved = not reasons
        module9 = self._module9_integration(
            approved=approved,
            reasons=reasons,
            module9_trigger_context=module9_trigger_context or {},
        )

        return RetrainingGuardReport(
            approved=approved,
            reasons=reasons if reasons else ["approved"],
            metrics={
                "suspicious_ratio": suspicious_ratio,
                "anomaly_rate": anomaly_rate,
                "dominant_class_ratio": dominant_ratio,
                "missing_provenance_rate": missing_provenance_rate,
            },
            module9_integration=module9,
        )

    @staticmethod
    def _module9_integration(*, approved: bool, reasons: list[str], module9_trigger_context: dict) -> dict[str, object]:
        """Emit integration hints consumable by Module 9 retraining flow."""

        base = {
            "module9_trigger_allowed": bool(approved),
            "module9_block_reasons": list(reasons),
            "trigger_context": dict(module9_trigger_context),
        }
        if approved:
            base["recommended_action"] = "continue_retraining_pipeline"
        else:
            base["recommended_action"] = "halt_retraining_and_quarantine_batch"
        return base
