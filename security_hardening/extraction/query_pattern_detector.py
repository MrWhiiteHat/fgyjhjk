"""Query pattern detector for model extraction and probing behavior."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class QueryRecord:
    """Recorded query sample used for pattern analysis."""

    timestamp: str
    input_digest: str
    threshold: float | None = None
    confidence: float | None = None
    tenant_id: str | None = None
    user_id: str | None = None
    ip: str | None = None


@dataclass
class QueryPatternResult:
    """Structured extraction risk analysis result."""

    suspicious: bool
    risk_score: float
    reason_codes: list[str] = field(default_factory=list)
    metadata: dict[str, float | str | int] = field(default_factory=dict)


class QueryPatternDetector:
    """Detects near-duplicate probing and confidence mapping attempts."""

    def analyze(
        self,
        *,
        history: list[QueryRecord],
        now_iso: str | None = None,
        window_seconds: int = 300,
        duplicate_hamming_threshold: int = 6,
        threshold_sweep_unique_count: int = 7,
        bulk_unique_inputs_threshold: int = 120,
    ) -> QueryPatternResult:
        """Analyze recent history for extraction-style query behavior."""

        now = self._parse_time(now_iso) if now_iso else datetime.now(tz=timezone.utc)
        recent = [record for record in history if (now - self._parse_time(record.timestamp)).total_seconds() <= window_seconds]

        if not recent:
            return QueryPatternResult(
                suspicious=False,
                risk_score=0.0,
                reason_codes=["insufficient_history"],
                metadata={"window_count": 0},
            )

        reasons: list[str] = []

        near_duplicate_pairs = self._count_near_duplicates(recent, duplicate_hamming_threshold)
        if near_duplicate_pairs >= 5:
            reasons.append("repeated_tiny_modifications")

        thresholds = [round(float(r.threshold), 4) for r in recent if r.threshold is not None]
        unique_thresholds = len(set(thresholds))
        if unique_thresholds >= threshold_sweep_unique_count:
            reasons.append("rapid_threshold_exploration")

        confidences = [float(r.confidence) for r in recent if r.confidence is not None]
        if len(confidences) >= 10:
            span = max(confidences) - min(confidences)
            if unique_thresholds >= 4 and span >= 0.4:
                reasons.append("confidence_distribution_probing")
        else:
            span = 0.0

        unique_inputs = len({r.input_digest for r in recent})
        if unique_inputs >= bulk_unique_inputs_threshold:
            reasons.append("bulk_enumeration_behavior")

        risk_score = min(
            1.0,
            0.30 * min(near_duplicate_pairs / 10.0, 1.0)
            + 0.25 * min(unique_thresholds / max(threshold_sweep_unique_count, 1), 1.0)
            + 0.20 * min(span / 0.6, 1.0)
            + 0.25 * min(unique_inputs / max(bulk_unique_inputs_threshold, 1), 1.0),
        )

        anchor = recent[-1]
        return QueryPatternResult(
            suspicious=bool(reasons),
            risk_score=risk_score,
            reason_codes=reasons if reasons else ["normal_query_pattern"],
            metadata={
                "window_count": len(recent),
                "near_duplicate_pairs": near_duplicate_pairs,
                "unique_thresholds": unique_thresholds,
                "confidence_span": round(span, 6),
                "unique_inputs": unique_inputs,
                "tenant_id": str(anchor.tenant_id or "unknown"),
                "user_id": str(anchor.user_id or "unknown"),
                "ip": str(anchor.ip or "unknown"),
            },
        )

    @staticmethod
    def _count_near_duplicates(records: list[QueryRecord], hamming_threshold: int) -> int:
        """Count near-duplicate digest pairs using hex-character hamming distance."""

        digests = [record.input_digest for record in records if record.input_digest]
        if len(digests) < 2:
            return 0

        count = 0
        for idx in range(len(digests)):
            for jdx in range(idx + 1, len(digests)):
                left = digests[idx]
                right = digests[jdx]
                if len(left) != len(right):
                    continue
                distance = sum(1 for a, b in zip(left, right) if a != b)
                if distance <= hamming_threshold:
                    count += 1
        return count

    @staticmethod
    def _parse_time(value: str | None) -> datetime:
        """Parse ISO timestamp into timezone-aware datetime."""

        if not value:
            return datetime.now(tz=timezone.utc)
        parsed = datetime.fromisoformat(str(value))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
