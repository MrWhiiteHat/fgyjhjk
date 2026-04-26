from pathlib import Path

import pytest

from ops.mlops.model_metadata import ModelMetadata
from ops.mlops.model_registry import ModelRegistry


def _build_metadata(artifact_path: Path, version: str) -> ModelMetadata:
    return ModelMetadata(
        model_name="detector",
        model_version=version,
        artifact_path=str(artifact_path.as_posix()),
        checkpoint_hash=ModelMetadata.compute_file_hash(artifact_path),
        created_at=ModelMetadata.now_iso(),
        trained_on_dataset="dataset_v1",
        validation_metrics={"auc": 0.95, "f1": 0.90},
        test_metrics={"auc": 0.94, "f1": 0.89},
        threshold=0.5,
        calibration_info={"method": "temperature"},
        promoted_stage="registered",
        notes="unit test",
    )


def test_model_registry_register_and_activate(tmp_path):
    artifact = tmp_path / "model.pt"
    artifact.write_bytes(b"fake-model")

    registry = ModelRegistry(registry_path=str(tmp_path / "registry.json"))
    metadata = _build_metadata(artifact, "v1")

    registry.register_model(metadata)
    loaded = registry.get_model("v1")

    assert loaded is not None
    assert loaded.model_version == "v1"
    assert registry.active_model_version() == "v1"

    registry.update_stage("v1", "production")
    assert registry.active_model_version() == "v1"


def test_model_registry_rejects_duplicate_version(tmp_path):
    artifact = tmp_path / "model.pt"
    artifact.write_bytes(b"fake-model")

    registry = ModelRegistry(registry_path=str(tmp_path / "registry.json"))
    metadata = _build_metadata(artifact, "v1")
    registry.register_model(metadata)

    with pytest.raises(ValueError):
        registry.register_model(metadata)
