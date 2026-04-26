"""Rate-shape guard for unusual request cadence patterns."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class RateShapeResult:
    """Cadence analysis result."""

    suspicious: bool
    reason_codes: list[str] = field(default_factory=list)
    stats: dict[str, float] = field(default_factory=dict)


class RateShapeGuard:
    """Detects non-human cadence and burst shapes for extraction mitigation."""

    def evaluate(
        self,
        *,
        timestamps: list[str],
        burst_rps_threshold: float = 4.0,
        min_jitter_threshold: float = 0.03,
    ) -> RateShapeResult:
        """Analyze request cadence by inter-arrival times."""

        if len(timestamps) < 3:
            return RateShapeResult(suspicious=False, reason_codes=["insufficient_samples"], stats={"count": float(len(timestamps))})

        ordered = sorted(self._parse(ts) for ts in timestamps)
        deltas = [max((ordered[i] - ordered[i - 1]).total_seconds(), 1e-6) for i in range(1, len(ordered))]

        mean_delta = sum(deltas) / len(deltas)
        jitter = (max(deltas) - min(deltas)) / max(mean_delta, 1e-6)
        rps = 1.0 / max(mean_delta, 1e-6)

        reasons: list[str] = []
        if rps >= burst_rps_threshold:
            reasons.append("cadence_rate_spike")
        if jitter <= min_jitter_threshold:
            reasons.append("cadence_too_regular")

        return RateShapeResult(
            suspicious=bool(reasons),
            reason_codes=reasons if reasons else ["cadence_normal"],
            stats={
                "mean_delta_seconds": mean_delta,
                "estimated_rps": rps,
                "jitter_ratio": jitter,
                "count": float(len(timestamps)),
            },
        )

    @staticmethod
    def _parse(value: str) -> datetime:
        """Parse ISO timestamp with UTC fallback."""

        parsed = datetime.fromisoformat(str(value))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
