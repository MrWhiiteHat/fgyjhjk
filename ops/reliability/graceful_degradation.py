"""Graceful degradation decisions under runtime stress or elevated risk."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class DegradationDecision:
    """Selected runtime mode and recommended action list."""

    mode: str
    reasons: List[str]
    actions: List[str]


class GracefulDegradationManager:
    """Determines reduced-service modes for resilience and safety."""

    def decide(
        self,
        resource_pressure: bool,
        circuit_open: bool,
        queue_overflow: bool,
        drift_alert: bool,
    ) -> DegradationDecision:
        reasons: List[str] = []
        if resource_pressure:
            reasons.append("resource_pressure")
        if circuit_open:
            reasons.append("dependency_circuit_open")
        if queue_overflow:
            reasons.append("queue_overflow")
        if drift_alert:
            reasons.append("drift_alert")

        if not reasons:
            return DegradationDecision(mode="normal", reasons=[], actions=[])

        if circuit_open or queue_overflow:
            return DegradationDecision(
                mode="safe_mode",
                reasons=reasons,
                actions=[
                    "serve_lightweight_predictions_only",
                    "disable_batch_uploads",
                    "tighten_rate_limits",
                ],
            )

        if resource_pressure or drift_alert:
            return DegradationDecision(
                mode="reduced_quality",
                reasons=reasons,
                actions=[
                    "disable_optional_postprocessing",
                    "skip_noncritical_logging_payloads",
                    "throttle_low_priority_requests",
                ],
            )

        return DegradationDecision(mode="normal", reasons=reasons, actions=[])

    @staticmethod
    def fallback_response(reason: str) -> Dict[str, object]:
        """Conservative response payload for temporary degraded states."""
        return {
            "status": "degraded",
            "prediction": "unknown",
            "confidence": 0.0,
            "reason": str(reason),
            "message": "Service is running in a protective degraded mode.",
        }
