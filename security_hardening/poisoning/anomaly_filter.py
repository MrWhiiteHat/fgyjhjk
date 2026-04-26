"""Feedback anomaly filter for coordinated and bursty submissions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class AnomalyFilterResult:
    """Anomaly detection output for feedback records."""

    suspicious_feedback_ids: list[str] = field(default_factory=list)
    reasons_by_feedback_id: dict[str, list[str]] = field(default_factory=dict)
    stats: dict[str, float] = field(default_factory=dict)


class AnomalyFilter:
    """Detects duplicate coordination, bursty activity, and low-quality corrections."""

    def detect(
        self,
        *,
        feedback_records: list[dict],
        burst_window_seconds: int = 120,
        burst_threshold: int = 25,
        low_quality_confidence_threshold: float = 0.35,
    ) -> AnomalyFilterResult:
        """Detect suspicious feedback patterns and return quarantinable IDs."""

        reasons: dict[str, list[str]] = {}

        by_signature: dict[str, list[str]] = {}
        by_actor_timestamps: dict[str, list[datetime]] = {}

        for record in feedback_records:
            feedback_id = str(record.get("feedback_id", "")).strip()
            if not feedback_id:
                continue

            actor = str(record.get("actor_id") or record.get("client_id") or "unknown")
            prediction_id = str(record.get("prediction_id", ""))
            corrected_label = str(record.get("corrected_label"))
            signature = f"{actor}|{prediction_id}|{corrected_label}"
            by_signature.setdefault(signature, []).append(feedback_id)

            ts = self._parse_time(record.get("submitted_at"))
            by_actor_timestamps.setdefault(actor, []).append(ts)

            confidence = record.get("correction_confidence")
            if confidence is not None and float(confidence) < float(low_quality_confidence_threshold):
                reasons.setdefault(feedback_id, []).append("low_quality_correction")

            provenance = record.get("provenance")
            if provenance in {None, "", "unknown"}:
                reasons.setdefault(feedback_id, []).append("missing_provenance")

        for _, ids in by_signature.items():
            if len(ids) > 1:
                for fid in ids:
                    reasons.setdefault(fid, []).append("duplicate_coordinated_feedback")

        for actor, timestamps in by_actor_timestamps.items():
            sorted_times = sorted(timestamps)
            for idx, current in enumerate(sorted_times):
                window_count = 1
                jdx = idx - 1
                while jdx >= 0 and (current - sorted_times[jdx]).total_seconds() <= burst_window_seconds:
                    window_count += 1
                    jdx -= 1
                if window_count >= burst_threshold:
                    for record in feedback_records:
                        rid = str(record.get("feedback_id", "")).strip()
                        ractor = str(record.get("actor_id") or record.get("client_id") or "unknown")
                        if rid and ractor == actor:
                            reasons.setdefault(rid, []).append("bursty_submission_pattern")
                    break

        suspicious_ids = sorted(reasons.keys())
        total = len([record for record in feedback_records if str(record.get("feedback_id", "")).strip()])
        anomaly_rate = len(suspicious_ids) / max(total, 1)

        return AnomalyFilterResult(
            suspicious_feedback_ids=suspicious_ids,
            reasons_by_feedback_id=reasons,
            stats={
                "total_feedback": float(total),
                "suspicious_feedback": float(len(suspicious_ids)),
                "anomaly_rate": float(anomaly_rate),
            },
        )

    @staticmethod
    def _parse_time(value: str | None) -> datetime:
        """Parse timestamp to timezone-aware datetime with UTC fallback."""

        if not value:
            return datetime.now(tz=timezone.utc)
        parsed = datetime.fromisoformat(str(value))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
