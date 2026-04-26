"""Canary release controller for staged traffic rollout."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass
class CanaryDecision:
    """Decision for canary request routing."""

    request_id: str
    use_candidate: bool
    traffic_percent: int


class CanaryRelease:
    """Traffic-gated canary release manager."""

    def route(self, *, request_id: str, traffic_percent: int) -> CanaryDecision:
        """Decide if request should hit candidate model by canary percentage."""

        clamped = min(max(int(traffic_percent), 0), 100)
        digest = hashlib.sha256(str(request_id).encode("utf-8")).hexdigest()
        bucket = int(digest[:8], 16) % 100
        use_candidate = bucket < clamped
        return CanaryDecision(request_id=str(request_id), use_candidate=use_candidate, traffic_percent=clamped)

    def evaluate_health(
        self,
        *,
        baseline_error_rate: float,
        candidate_error_rate: float,
        baseline_latency_ms: float,
        candidate_latency_ms: float,
        max_error_spike: float,
        max_latency_spike: float,
    ) -> tuple[bool, list[str]]:
        """Validate canary health against error and latency spike thresholds."""

        reasons: list[str] = []
        if candidate_error_rate - baseline_error_rate > float(max_error_spike):
            reasons.append("canary_error_spike")
        if candidate_latency_ms - baseline_latency_ms > float(max_latency_spike):
            reasons.append("canary_latency_spike")
        return (not reasons), reasons
