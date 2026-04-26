"""Model promotion workflow with validation and deployment tracking."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, Optional

import yaml

from ops.mlops.artifact_store import ArtifactStore
from ops.mlops.deployment_tracker import DeploymentTracker
from ops.mlops.model_registry import ModelRegistry
from ops.mlops.model_validation_gate import ModelValidationGate


class ModelPromotionService:
    """Promotes model versions across stages with policy controls."""

    def __init__(
        self,
        registry: ModelRegistry | None = None,
        artifact_store: ArtifactStore | None = None,
        validation_gate: ModelValidationGate | None = None,
        tracker: DeploymentTracker | None = None,
        mlops_config_path: str = "ops/configs/mlops_config.yaml",
        ops_config_path: str = "ops/configs/ops_config.yaml",
    ) -> None:
        self.registry = registry or ModelRegistry()
        self.artifact_store = artifact_store or ArtifactStore()
        self.validation_gate = validation_gate or ModelValidationGate(config_path=mlops_config_path)
        self.tracker = tracker or DeploymentTracker()

        self.mlops_config_path = Path(mlops_config_path)
        self.ops_config_path = Path(ops_config_path)
        self.mlops_config = self._load_config(self.mlops_config_path)

    @staticmethod
    def _load_config(path: Path) -> Dict[str, object]:
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
        return payload if isinstance(payload, dict) else {}

    def _require_approval_if_needed(self, approval_token: str | None) -> None:
        if bool(self.mlops_config.get("promotion_requires_approval", False)) and not approval_token:
            raise PermissionError("Promotion approval is required by policy")

    def _update_ops_active_version(self, model_version: str) -> None:
        payload = self._load_config(self.ops_config_path)
        payload["active_model_version"] = str(model_version)
        with self.ops_config_path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(payload, handle, sort_keys=False)

    def promote(
        self,
        model_version: str,
        target_stage: str,
        actor: str,
        reason: str,
        approval_token: str | None = None,
        cache_invalidator: Optional[Callable[[], None]] = None,
    ) -> Dict[str, object]:
        """Promote model to staging/production/archived according to policy."""
        stage = str(target_stage)
        if stage not in {"staging", "production", "archived"}:
            raise ValueError(f"Unsupported target stage: {stage}")

        self._require_approval_if_needed(approval_token)

        metadata = self.registry.get_model(model_version)
        if metadata is None:
            raise ValueError(f"Model version not found in registry: {model_version}")

        if bool(self.mlops_config.get("model_validation_required", True)) and stage in {"staging", "production"}:
            validation = self.validation_gate.validate_candidate(metadata, artifact_store=self.artifact_store)
            if not validation.get("passed", False):
                self.tracker.record(
                    action="promotion",
                    model_version=model_version,
                    stage=stage,
                    actor=actor,
                    reason=reason,
                    outcome="blocked",
                    metadata={"validation": validation},
                )
                raise RuntimeError(f"Model promotion blocked by validation gate: {validation['failed_checks']}")

        self.registry.update_stage(model_version, stage)
        if stage == "production":
            self.registry.set_active_model_version(model_version)
            self._update_ops_active_version(model_version)
            if cache_invalidator is not None:
                cache_invalidator()

        event = self.tracker.record(
            action="promotion",
            model_version=model_version,
            stage=stage,
            actor=actor,
            reason=reason,
            outcome="success",
            metadata={"approval_used": bool(approval_token)},
        )
        return event
