"""Rollout and rollback safety tests."""

from __future__ import annotations

from pathlib import Path

from ml_lifecycle.registry.artifact_store import ArtifactStore
from ml_lifecycle.registry.model_registry import ModelRegistry
from ml_lifecycle.rollout.ab_testing import ABTesting
from ml_lifecycle.rollout.canary_release import CanaryRelease
from ml_lifecycle.rollout.rollback_manager import RollbackManager
from ml_lifecycle.rollout.shadow_deploy import ShadowDeploy


class ThresholdModel:
    def __init__(self, threshold: float) -> None:
        self._threshold = threshold

    def predict(self, features: dict[str, float]) -> int:
        return 1 if float(features.get("x", 0.0)) >= self._threshold else 0


def test_shadow_and_canary_health() -> None:
    prod = ThresholdModel(0.6)
    cand = ThresholdModel(0.55)

    requests = [
        {"features": {"x": 0.2}, "label": 0, "production_latency_ms": 20.0, "candidate_latency_ms": 25.0},
        {"features": {"x": 0.8}, "label": 1, "production_latency_ms": 21.0, "candidate_latency_ms": 26.0},
        {"features": {"x": 0.58}, "label": 1, "production_latency_ms": 22.0, "candidate_latency_ms": 27.0},
    ]

    shadow = ShadowDeploy().evaluate(production_model=prod, candidate_model=cand, requests=requests)
    assert shadow.total_requests == 3

    canary = CanaryRelease()
    healthy, reasons = canary.evaluate_health(
        baseline_error_rate=0.10,
        candidate_error_rate=0.11,
        baseline_latency_ms=20.0,
        candidate_latency_ms=25.0,
        max_error_spike=0.05,
        max_latency_spike=10.0,
    )
    assert healthy is True
    assert reasons == []


def test_rollback_triggered_on_error_spike(tmp_path: Path) -> None:
    registry = ModelRegistry(artifact_store=ArtifactStore(root_dir=tmp_path / "artifacts"))

    v1 = registry.register_model(
        training_dataset_id="ds_v1",
        metrics={"accuracy": 0.90},
        created_at="2026-04-18T00:00:00+00:00",
        payload=b"v1",
    )
    registry.promote_model(model_version=v1.model_version, promoted_at="2026-04-18T00:01:00+00:00", validation_passed=True)

    v2 = registry.register_model(
        training_dataset_id="ds_v2",
        metrics={"accuracy": 0.91},
        created_at="2026-04-18T00:02:00+00:00",
        payload=b"v2",
    )
    registry.promote_model(model_version=v2.model_version, promoted_at="2026-04-18T00:03:00+00:00", validation_passed=True)

    manager = RollbackManager(registry)
    result = manager.evaluate_and_rollback(
        current_metrics={"error_rate": 0.30, "latency_ms": 80.0, "accuracy": 0.70},
        baseline_metrics={"error_rate": 0.10, "latency_ms": 40.0, "accuracy": 0.90},
        rollback_thresholds={
            "error_rate_spike_threshold": 0.05,
            "latency_spike_ms_threshold": 30.0,
            "metric_degradation_threshold": 0.05,
        },
        timestamp="2026-04-18T00:04:00+00:00",
    )

    assert result.triggered is True
    assert result.target_version == v1.model_version
    assert registry.get_production_model().model_version == v1.model_version


def test_ab_assignment_is_deterministic() -> None:
    ab = ABTesting()
    a1 = ab.assign(request_id="same-request", control_ratio=0.5)
    a2 = ab.assign(request_id="same-request", control_ratio=0.5)
    assert a1.bucket == a2.bucket
