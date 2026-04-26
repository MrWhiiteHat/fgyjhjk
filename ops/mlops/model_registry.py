"""File-based model registry with version and stage indexing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from ops.mlops.model_metadata import ModelMetadata


class ModelRegistry:
    """JSON-backed registry for model metadata and active deployment version."""

    def __init__(self, registry_path: str = "ops/mlops/state/model_registry.json") -> None:
        self.registry_path = Path(registry_path)
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.registry_path.exists():
            self._save(
                {
                    "model_name": "",
                    "active_model_version": "",
                    "models": {},
                    "history": [],
                }
            )

    def _load(self) -> Dict[str, object]:
        with self.registry_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValueError("Registry payload must be a dictionary")
        payload.setdefault("models", {})
        payload.setdefault("history", [])
        payload.setdefault("active_model_version", "")
        payload.setdefault("model_name", "")
        return payload

    def _save(self, payload: Dict[str, object]) -> None:
        with self.registry_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)

    def register_model(self, metadata: ModelMetadata, allow_overwrite: bool = False) -> Dict[str, object]:
        """Register model version in registry with collision protection."""
        checks = metadata.validate()
        if not checks.get("valid", False):
            raise ValueError(f"Invalid model metadata: {checks}")

        payload = self._load()
        models = dict(payload.get("models", {}))
        if metadata.model_version in models and not allow_overwrite:
            raise ValueError(f"Model version collision: {metadata.model_version}")

        payload["model_name"] = metadata.model_name
        models[metadata.model_version] = metadata.to_dict()
        payload["models"] = models
        payload["history"].append(
            {
                "event": "register_model",
                "model_version": metadata.model_version,
                "stage": metadata.promoted_stage,
                "timestamp": metadata.created_at,
            }
        )
        if not payload.get("active_model_version"):
            payload["active_model_version"] = metadata.model_version

        self._save(payload)
        return metadata.to_dict()

    def get_model(self, model_version: str) -> Optional[ModelMetadata]:
        payload = self._load()
        models = dict(payload.get("models", {}))
        model_data = models.get(str(model_version))
        if model_data is None:
            return None
        return ModelMetadata.from_dict(model_data)

    def list_models(self, stage: str | None = None) -> List[Dict[str, object]]:
        payload = self._load()
        models = dict(payload.get("models", {}))
        items = []
        for version, model_data in models.items():
            metadata = dict(model_data)
            metadata["model_version"] = version
            if stage is not None and str(metadata.get("promoted_stage", "")) != str(stage):
                continue
            items.append(metadata)
        return sorted(items, key=lambda item: str(item.get("model_version", "")))

    def active_model_version(self) -> str:
        payload = self._load()
        return str(payload.get("active_model_version", ""))

    def set_active_model_version(self, model_version: str) -> None:
        payload = self._load()
        models = dict(payload.get("models", {}))
        if str(model_version) not in models:
            raise ValueError(f"Unknown model version: {model_version}")
        payload["active_model_version"] = str(model_version)
        payload["history"].append(
            {
                "event": "set_active_model_version",
                "model_version": str(model_version),
                "timestamp": ModelMetadata.now_iso(),
            }
        )
        self._save(payload)

    def update_stage(self, model_version: str, stage: str) -> None:
        stage_value = str(stage)
        if stage_value not in {"registered", "staging", "production", "archived"}:
            raise ValueError(f"Invalid stage: {stage_value}")

        payload = self._load()
        models = dict(payload.get("models", {}))
        if str(model_version) not in models:
            raise ValueError(f"Unknown model version: {model_version}")

        model_data = dict(models[str(model_version)])
        model_data["promoted_stage"] = stage_value
        models[str(model_version)] = model_data
        payload["models"] = models

        payload["history"].append(
            {
                "event": "update_stage",
                "model_version": str(model_version),
                "stage": stage_value,
                "timestamp": ModelMetadata.now_iso(),
            }
        )

        if stage_value == "production":
            payload["active_model_version"] = str(model_version)

        self._save(payload)
