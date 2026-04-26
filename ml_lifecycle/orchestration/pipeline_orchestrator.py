"""End-to-end ML lifecycle orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field

from ml_lifecycle.evaluation.model_validator import ModelValidator, ValidationResult
from ml_lifecycle.monitoring.alert_rules import Alert, AlertRules
from ml_lifecycle.monitoring.drift_detector import DriftDetector
from ml_lifecycle.monitoring.metrics_store import InferenceRecord
from ml_lifecycle.orchestration.state_machine import LifecycleStateMachine
from ml_lifecycle.registry.model_registry import ModelRecord, ModelRegistry
from ml_lifecycle.retraining.retrain_pipeline import RetrainPipeline
from ml_lifecycle.retraining.training_trigger import TrainingTrigger
from ml_lifecycle.rollout.canary_release import CanaryRelease
from ml_lifecycle.rollout.shadow_deploy import ShadowDeploy


@dataclass
class OrchestrationResult:
    """Aggregated output of a lifecycle orchestration cycle."""

    final_state: str
    alerts: list[Alert] = field(default_factory=list)
    drift_report: dict = field(default_factory=dict)
    trigger_reasons: list[str] = field(default_factory=list)
    candidate_version: str | None = None
    validation_passed: bool = False
    rollout_passed: bool = False


class PipelineOrchestrator:
    """Coordinates monitoring, retraining, validation, and rollout stages."""

    def __init__(
        self,
        *,
        registry: ModelRegistry,
        drift_detector: DriftDetector | None = None,
        training_trigger: TrainingTrigger | None = None,
        retrain_pipeline: RetrainPipeline | None = None,
        validator: ModelValidator | None = None,
        shadow_deploy: ShadowDeploy | None = None,
        canary_release: CanaryRelease | None = None,
        alert_rules: AlertRules | None = None,
        state_machine: LifecycleStateMachine | None = None,
    ) -> None:
        self._registry = registry
        self._drift_detector = drift_detector or DriftDetector()
        self._trigger = training_trigger or TrainingTrigger()
        self._retrain = retrain_pipeline or RetrainPipeline()
        self._validator = validator or ModelValidator()
        self._shadow = shadow_deploy or ShadowDeploy()
        self._canary = canary_release or CanaryRelease()
        self._alert_rules = alert_rules or AlertRules()
        self._state = state_machine or LifecycleStateMachine()

    def run_cycle(
        self,
        *,
        reference_records: list[InferenceRecord],
        current_records: list[InferenceRecord],
        original_samples: list[dict],
        new_samples: list[dict],
        corrected_labels: list,
        validation_samples: list[dict],
        regression_cases: list[dict],
        acceptance_criteria: dict,
        retrain_config: dict,
        rollout_config: dict,
        now_iso: str,
        last_retrain_at: str | None,
        feedback_volume: int,
        production_model,
        shadow_requests: list[dict],
        candidate_latency_ms: float,
        production_latency_ms: float,
    ) -> OrchestrationResult:
        """Execute one full lifecycle cycle and return final outcomes."""

        alerts: list[Alert] = []

        self._state.transition("monitoring")
        drift_report = self._drift_detector.detect(reference=reference_records, current=current_records)
        alerts.extend(drift_report.get("alerts", []))

        drift_alerted = bool(drift_report.get("alerts"))
        if drift_alerted:
            self._state.transition("drift_detected")

        decision = self._trigger.should_trigger(
            drift_report=drift_report,
            last_retrain_at=last_retrain_at,
            now_iso=now_iso,
            feedback_volume=feedback_volume,
            config=retrain_config,
        )

        if not decision.should_trigger:
            self._state.transition("production")
            return OrchestrationResult(
                final_state=self._state.state,
                alerts=alerts,
                drift_report=drift_report,
                trigger_reasons=[],
            )

        alerts.append(self._alert_rules.retraining_triggered(reason=",".join(decision.reasons)))

        if self._state.state != "drift_detected":
            self._state.transition("drift_detected")
        self._state.transition("retraining")

        retrain_output = self._retrain.run(
            original_samples=original_samples,
            new_samples=new_samples,
            corrected_labels=corrected_labels,
            config=retrain_config,
        )

        candidate_model = retrain_output["model"]
        registered: ModelRecord = self._registry.register_model(
            training_dataset_id=retrain_output["training_dataset_id"],
            metrics={k: float(v) for k, v in retrain_output["metrics"].items() if isinstance(v, (int, float))},
            created_at=now_iso,
            payload=retrain_output["artifact_bytes"],
            metadata={"trigger_reasons": ",".join(decision.reasons)},
        )

        self._state.transition("validation")
        validation: ValidationResult = self._validator.validate(
            candidate_model=candidate_model,
            production_model=production_model,
            validation_samples=validation_samples,
            regression_cases=regression_cases,
            acceptance_criteria=acceptance_criteria,
            candidate_latency_ms=float(candidate_latency_ms),
            production_latency_ms=float(production_latency_ms),
        )

        if not validation.passed:
            alerts.append(self._alert_rules.failed_validation(details="; ".join(validation.reasons)))
            self._state.transition("monitoring")
            return OrchestrationResult(
                final_state=self._state.state,
                alerts=alerts,
                drift_report=drift_report,
                trigger_reasons=decision.reasons,
                candidate_version=registered.model_version,
                validation_passed=False,
                rollout_passed=False,
            )

        self._state.transition("rollout")
        shadow = self._shadow.evaluate(
            production_model=production_model,
            candidate_model=candidate_model,
            requests=shadow_requests,
        )

        rollback_cfg = dict(rollout_config.get("rollback") or {})
        healthy, failure_reasons = self._canary.evaluate_health(
            baseline_error_rate=float(1.0 - (shadow.production_accuracy if shadow.production_accuracy is not None else 1.0)),
            candidate_error_rate=float(1.0 - (shadow.candidate_accuracy if shadow.candidate_accuracy is not None else 1.0)),
            baseline_latency_ms=float(shadow.production_latency_ms),
            candidate_latency_ms=float(shadow.candidate_latency_ms),
            max_error_spike=float(rollback_cfg.get("error_rate_spike_threshold", 0.05)),
            max_latency_spike=float(rollback_cfg.get("latency_spike_ms_threshold", 40.0)),
        )

        if not healthy:
            alerts.append(self._alert_rules.failed_rollout(details=",".join(failure_reasons)))
            self._state.transition("monitoring")
            return OrchestrationResult(
                final_state=self._state.state,
                alerts=alerts,
                drift_report=drift_report,
                trigger_reasons=decision.reasons,
                candidate_version=registered.model_version,
                validation_passed=True,
                rollout_passed=False,
            )

        self._registry.promote_model(
            model_version=registered.model_version,
            promoted_at=now_iso,
            validation_passed=True,
        )

        self._state.transition("production")
        return OrchestrationResult(
            final_state=self._state.state,
            alerts=alerts,
            drift_report=drift_report,
            trigger_reasons=decision.reasons,
            candidate_version=registered.model_version,
            validation_passed=True,
            rollout_passed=True,
        )
