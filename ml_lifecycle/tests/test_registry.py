"""Registry versioning, promotion, and rollback tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from ml_lifecycle.registry.artifact_store import ArtifactStore
from ml_lifecycle.registry.model_registry import ModelRegistry


def test_register_promote_and_rollback(tmp_path: Path) -> None:
    store = ArtifactStore(root_dir=tmp_path / "artifacts")
    registry = ModelRegistry(artifact_store=store)

    m1 = registry.register_model(
        training_dataset_id="ds_1",
        metrics={"accuracy": 0.90},
        created_at="2026-04-18T00:00:00+00:00",
        payload=b"model-1",
    )
    m2 = registry.register_model(
        training_dataset_id="ds_2",
        metrics={"accuracy": 0.92},
        created_at="2026-04-18T01:00:00+00:00",
        payload=b"model-2",
    )

    promoted_v1 = registry.promote_model(
        model_version=m1.model_version,
        promoted_at="2026-04-18T01:10:00+00:00",
        validation_passed=True,
    )
    assert promoted_v1.status == "production"

    promoted_v2 = registry.promote_model(
        model_version=m2.model_version,
        promoted_at="2026-04-18T02:00:00+00:00",
        validation_passed=True,
    )
    assert promoted_v2.status == "production"
    assert registry.get_production_model() is not None
    assert registry.get_production_model().model_version == m2.model_version

    rolled = registry.rollback_model(rollback_at="2026-04-18T03:00:00+00:00")
    assert rolled.model_version == m1.model_version
    assert registry.get_production_model().model_version == m1.model_version


def test_unvalidated_model_cannot_be_promoted(tmp_path: Path) -> None:
    store = ArtifactStore(root_dir=tmp_path / "artifacts")
    registry = ModelRegistry(artifact_store=store)

    staged = registry.register_model(
        training_dataset_id="ds_3",
        metrics={"accuracy": 0.88},
        created_at="2026-04-18T04:00:00+00:00",
        payload=b"model-3",
    )

    with pytest.raises(ValueError):
        registry.promote_model(
            model_version=staged.model_version,
            promoted_at="2026-04-18T04:10:00+00:00",
            validation_passed=False,
        )
