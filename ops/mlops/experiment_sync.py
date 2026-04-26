"""Sync training/evaluation outputs into registry metadata entries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

from ops.mlops.model_metadata import ModelMetadata, load_metrics_from_report
from ops.mlops.model_registry import ModelRegistry


class ExperimentSync:
    """Builds registry metadata from existing experiment artifacts."""

    def __init__(self, registry: ModelRegistry | None = None) -> None:
        self.registry = registry or ModelRegistry()

    @staticmethod
    def _find_latest_report(root: Path, filename: str) -> Optional[Path]:
        candidates = sorted(root.rglob(filename))
        return candidates[-1] if candidates else None

    def sync_from_outputs(
        self,
        model_name: str,
        model_version: str,
        artifact_path: str,
        dataset_name: str = "unknown_dataset",
        notes: str = "synced from existing outputs",
        allow_overwrite: bool = False,
    ) -> Dict[str, object]:
        training_reports_root = Path("training/outputs/reports")
        validation_report = self._find_latest_report(training_reports_root, "final_experiment_report.json")
        test_summary = self._find_latest_report(training_reports_root, "test_summary_metrics_only.json")

        validation_metrics = load_metrics_from_report(validation_report) if validation_report else {}
        test_metrics = load_metrics_from_report(test_summary) if test_summary else {}

        metadata = ModelMetadata(
            model_name=model_name,
            model_version=model_version,
            artifact_path=str(Path(artifact_path).as_posix()),
            checkpoint_hash=ModelMetadata.compute_file_hash(artifact_path),
            created_at=ModelMetadata.now_iso(),
            trained_on_dataset=dataset_name,
            validation_metrics=validation_metrics,
            test_metrics=test_metrics,
            threshold=0.5,
            calibration_info={
                "source": "training outputs",
                "available": True if validation_report else False,
            },
            promoted_stage="registered",
            notes=notes,
        )

        return self.registry.register_model(metadata, allow_overwrite=allow_overwrite)
