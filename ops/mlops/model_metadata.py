"""Model metadata schema and validation helpers."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional


@dataclass
class ModelMetadata:
    """Normalized model metadata used by registry and promotion workflows."""

    model_name: str
    model_version: str
    artifact_path: str
    checkpoint_hash: str
    created_at: str
    trained_on_dataset: str
    validation_metrics: Dict[str, float]
    test_metrics: Dict[str, float]
    threshold: float
    calibration_info: Dict[str, object]
    promoted_stage: str
    notes: str = ""

    @staticmethod
    def now_iso() -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    @staticmethod
    def compute_file_hash(file_path: str | Path, chunk_size: int = 65536) -> str:
        digest = hashlib.sha256()
        with Path(file_path).open("rb") as handle:
            while True:
                chunk = handle.read(chunk_size)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()

    def validate(self) -> Dict[str, object]:
        checks = {
            "has_model_name": bool(self.model_name),
            "has_model_version": bool(self.model_version),
            "has_artifact_path": bool(self.artifact_path),
            "artifact_exists": Path(self.artifact_path).exists(),
            "threshold_valid": 0.0 <= float(self.threshold) <= 1.0,
            "has_validation_metrics": isinstance(self.validation_metrics, dict) and len(self.validation_metrics) > 0,
            "has_test_metrics": isinstance(self.test_metrics, dict) and len(self.test_metrics) > 0,
            "stage_valid": self.promoted_stage in {"registered", "staging", "production", "archived"},
        }
        checks["valid"] = all(checks.values())
        return checks

    def to_dict(self) -> Dict[str, object]:
        return {
            "model_name": self.model_name,
            "model_version": self.model_version,
            "artifact_path": self.artifact_path,
            "checkpoint_hash": self.checkpoint_hash,
            "created_at": self.created_at,
            "trained_on_dataset": self.trained_on_dataset,
            "validation_metrics": self.validation_metrics,
            "test_metrics": self.test_metrics,
            "threshold": float(self.threshold),
            "calibration_info": self.calibration_info,
            "promoted_stage": self.promoted_stage,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "ModelMetadata":
        return cls(
            model_name=str(payload.get("model_name", "")),
            model_version=str(payload.get("model_version", "")),
            artifact_path=str(payload.get("artifact_path", "")),
            checkpoint_hash=str(payload.get("checkpoint_hash", "")),
            created_at=str(payload.get("created_at", cls.now_iso())),
            trained_on_dataset=str(payload.get("trained_on_dataset", "")),
            validation_metrics={k: float(v) for k, v in dict(payload.get("validation_metrics", {})).items()},
            test_metrics={k: float(v) for k, v in dict(payload.get("test_metrics", {})).items()},
            threshold=float(payload.get("threshold", 0.5)),
            calibration_info=dict(payload.get("calibration_info", {})),
            promoted_stage=str(payload.get("promoted_stage", "registered")),
            notes=str(payload.get("notes", "")),
        )


def load_metrics_from_report(report_path: str | Path) -> Dict[str, float]:
    """Load numeric metrics from JSON report."""
    path = Path(report_path)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}

    metrics: Dict[str, float] = {}
    for key, value in payload.items():
        try:
            metrics[str(key)] = float(value)
        except (TypeError, ValueError):
            continue
    return metrics
