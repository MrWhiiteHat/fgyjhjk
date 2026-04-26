"""Rollback controller for rapid recovery from rollout regressions."""

from __future__ import annotations

from dataclasses import dataclass

from ml_lifecycle.registry.model_registry import ModelRegistry


@dataclass
class RollbackResult:
    """Rollback action result payload."""

    triggered: bool
    reasons: list[str]
    target_version: str | None


class RollbackManager:
    """Evaluates rollout health and performs instant rollback when needed."""

    def __init__(self, registry: ModelRegistry) -> None:
        self._registry = registry

    def evaluate_and_rollback(
        self,
        *,
        current_metrics: dict[str, float],
        baseline_metrics: dict[str, float],
        rollback_thresholds: dict[str, float],
        timestamp: str,
    ) -> RollbackResult:
        """Trigger rollback when error, latency, or accuracy degradation thresholds are exceeded."""

        reasons: list[str] = []

        current_error = float(current_metrics.get("error_rate", 0.0))
        baseline_error = float(baseline_metrics.get("error_rate", 0.0))
        error_spike = current_error - baseline_error

        current_latency = float(current_metrics.get("latency_ms", 0.0))
        baseline_latency = float(baseline_metrics.get("latency_ms", 0.0))
        latency_spike = current_latency - baseline_latency

        current_accuracy = float(current_metrics.get("accuracy", 0.0))
        baseline_accuracy = float(baseline_metrics.get("accuracy", 0.0))
        metric_degradation = baseline_accuracy - current_accuracy

        if error_spike > float(rollback_thresholds.get("error_rate_spike_threshold", 0.05)):
            reasons.append("error_spike")
        if latency_spike > float(rollback_thresholds.get("latency_spike_ms_threshold", 40.0)):
            reasons.append("latency_spike")
        if metric_degradation > float(rollback_thresholds.get("metric_degradation_threshold", 0.02)):
            reasons.append("metric_degradation")

        if not reasons:
            return RollbackResult(triggered=False, reasons=[], target_version=None)

        rolled = self._registry.rollback_model(rollback_at=timestamp)
        return RollbackResult(triggered=True, reasons=reasons, target_version=rolled.model_version)
