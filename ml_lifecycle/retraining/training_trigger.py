"""Retraining trigger policy evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class TriggerDecision:
    """Decision payload for retraining trigger checks."""

    should_trigger: bool
    reasons: list[str]


class TrainingTrigger:
    """Evaluates drift, time-based, and feedback-volume retrain triggers."""

    def should_trigger(
        self,
        *,
        drift_report: dict,
        last_retrain_at: str | None,
        now_iso: str,
        feedback_volume: int,
        config: dict,
    ) -> TriggerDecision:
        """Return trigger decision from configured lifecycle conditions."""

        reasons: list[str] = []

        drift_cfg = dict(config.get("drift_trigger") or {})
        data_threshold = float(drift_cfg.get("data_drift_score_threshold", 0.2))
        conf_threshold = float(drift_cfg.get("concept_confidence_shift_threshold", 0.1))
        err_threshold = float(drift_cfg.get("concept_error_rate_delta_threshold", 0.05))

        data_score = float(((drift_report.get("data_drift") or {}).get("aggregate_score") or 0.0))
        concept = drift_report.get("concept_drift") or {}
        confidence_shift = float(concept.get("confidence_shift") or 0.0)
        error_delta = concept.get("error_rate_delta")
        error_delta_value = float(error_delta) if error_delta is not None else 0.0

        if data_score >= data_threshold:
            reasons.append("drift:data_drift")
        if confidence_shift >= conf_threshold:
            reasons.append("drift:confidence_shift")
        if error_delta is not None and error_delta_value >= err_threshold:
            reasons.append("drift:error_rate_delta")

        time_cfg = dict(config.get("time_trigger") or {})
        min_days = int(time_cfg.get("min_days_between_retrains", 7))
        if last_retrain_at is None:
            reasons.append("time:first_retrain")
        else:
            now = datetime.fromisoformat(now_iso)
            last = datetime.fromisoformat(last_retrain_at)
            if now.tzinfo is None:
                now = now.replace(tzinfo=timezone.utc)
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            elapsed_days = (now - last).total_seconds() / (24 * 60 * 60)
            if elapsed_days >= min_days:
                reasons.append("time:interval_elapsed")

        feedback_cfg = dict(config.get("feedback_trigger") or {})
        min_feedback = int(feedback_cfg.get("min_feedback_records", 50))
        if int(feedback_volume) >= min_feedback:
            reasons.append("feedback:volume_threshold")

        return TriggerDecision(should_trigger=bool(reasons), reasons=reasons)
