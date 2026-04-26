"""Rollback manager for selecting and restoring prior production model versions."""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

from ops.mlops.deployment_tracker import DeploymentTracker
from ops.mlops.model_registry import ModelRegistry


class RollbackManager:
    """Provides rollback candidate listing and active model reversion."""

    def __init__(self, registry: ModelRegistry | None = None, tracker: DeploymentTracker | None = None) -> None:
        self.registry = registry or ModelRegistry()
        self.tracker = tracker or DeploymentTracker()

    def list_rollback_candidates(self, limit: int = 10) -> List[Dict[str, object]]:
        """List recent successful production deployments as rollback candidates."""
        events = self.tracker.production_events(limit=500)
        candidates: List[Dict[str, object]] = []
        for event in reversed(events):
            if str(event.get("outcome")) != "success":
                continue
            model_version = str(event.get("model_version", ""))
            metadata = self.registry.get_model(model_version)
            if metadata is None:
                continue
            candidates.append(
                {
                    "model_version": model_version,
                    "timestamp": event.get("timestamp"),
                    "actor": event.get("actor"),
                    "reason": event.get("reason"),
                    "stage": event.get("stage"),
                    "artifact_path": metadata.artifact_path,
                }
            )
            if len(candidates) >= int(limit):
                break
        return candidates

    def rollback_to_version(
        self,
        target_version: str,
        actor: str,
        reason: str,
        cache_invalidator: Optional[Callable[[], None]] = None,
    ) -> Dict[str, object]:
        """Rollback active production model to explicit version."""
        metadata = self.registry.get_model(target_version)
        if metadata is None:
            raise ValueError(f"Rollback target not found in registry: {target_version}")

        self.registry.update_stage(target_version, "production")
        self.registry.set_active_model_version(target_version)
        if cache_invalidator is not None:
            cache_invalidator()

        event = self.tracker.record(
            action="rollback",
            model_version=target_version,
            stage="production",
            actor=actor,
            reason=reason,
            outcome="success",
            metadata={"rollback_target": target_version},
        )
        return event

    def rollback_to_previous(
        self,
        actor: str,
        reason: str,
        cache_invalidator: Optional[Callable[[], None]] = None,
    ) -> Dict[str, object]:
        """Rollback to previous production model based on deployment history."""
        active = self.registry.active_model_version()
        candidates = self.list_rollback_candidates(limit=20)

        for candidate in candidates:
            version = str(candidate.get("model_version", ""))
            if version and version != active:
                return self.rollback_to_version(
                    target_version=version,
                    actor=actor,
                    reason=reason,
                    cache_invalidator=cache_invalidator,
                )

        raise RuntimeError("No rollback candidate available")
