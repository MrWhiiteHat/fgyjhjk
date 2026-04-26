"""Validation gate enforcing quality thresholds before model promotion."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import yaml

from ops.mlops.artifact_store import ArtifactStore
from ops.mlops.model_metadata import ModelMetadata


class ModelValidationGate:
    """Runs deterministic checks to allow or block model promotion."""

    def __init__(self, config_path: str = "ops/configs/mlops_config.yaml") -> None:
        self.config_path = Path(config_path)
        self.config = self._load_config(self.config_path)
        self.min_metrics = dict(self.config.get("minimum_validation_metrics", {}))
        self.required_report_files = list(self.config.get("required_report_files", []))

    @staticmethod
    def _load_config(path: Path) -> Dict[str, object]:
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
        return payload if isinstance(payload, dict) else {}

    def _check_metrics(self, metadata: ModelMetadata) -> List[Dict[str, object]]:
        checks = []
        for metric_name, required in self.min_metrics.items():
            observed = float(metadata.validation_metrics.get(metric_name, float("nan")))
            passed = observed >= float(required) if observed == observed else False
            checks.append(
                {
                    "check": f"metric_{metric_name}",
                    "passed": bool(passed),
                    "required": float(required),
                    "observed": observed,
                }
            )
        return checks

    def _check_reports(self, metadata: ModelMetadata) -> List[Dict[str, object]]:
        report_base = Path("training/outputs/reports")
        checks = []
        if not self.required_report_files:
            return checks

        candidate_dirs = [item for item in report_base.glob("**/") if item.is_dir()]
        for required in self.required_report_files:
            found = any((directory / required).exists() for directory in candidate_dirs)
            checks.append({"check": f"required_report_{required}", "passed": bool(found)})
        return checks

    def _smoke_load(self, metadata: ModelMetadata) -> Dict[str, object]:
        smoke_cfg = dict(self.config.get("inference_smoke_test", {}))
        if not bool(smoke_cfg.get("enabled", False)):
            return {"check": "inference_smoke_test", "passed": True, "skipped": True}

        artifact = Path(metadata.artifact_path)
        if not artifact.exists():
            return {"check": "inference_smoke_test", "passed": False, "reason": "artifact_missing"}

        suffix = artifact.suffix.lower()
        if suffix not in {".pt", ".pth", ".onnx", ".ts"}:
            return {"check": "inference_smoke_test", "passed": True, "skipped": True, "reason": "unsupported_suffix"}

        try:
            if suffix in {".pt", ".pth", ".ts"}:
                import torch

                _ = torch.load(str(artifact), map_location="cpu")
            elif suffix == ".onnx":
                import onnxruntime as ort

                _ = ort.InferenceSession(str(artifact), providers=["CPUExecutionProvider"])
            return {"check": "inference_smoke_test", "passed": True}
        except Exception as exc:  # noqa: BLE001
            return {"check": "inference_smoke_test", "passed": False, "reason": str(exc)}

    def validate_candidate(self, metadata: ModelMetadata, artifact_store: ArtifactStore | None = None) -> Dict[str, object]:
        """Run gate checks and return pass/fail decision with reasons."""
        checks: List[Dict[str, object]] = []

        artifact_path = Path(metadata.artifact_path)
        checks.append(
            {
                "check": "artifact_exists",
                "passed": artifact_path.exists() and artifact_path.is_file(),
                "artifact_path": str(artifact_path.as_posix()),
            }
        )

        if artifact_store is not None and artifact_path.exists():
            checks.append(
                {
                    "check": "artifact_store_reachable",
                    "passed": artifact_store.root_path.exists(),
                    "artifact_store": str(artifact_store.root_path.as_posix()),
                }
            )

        checks.extend(self._check_metrics(metadata))
        checks.extend(self._check_reports(metadata))
        checks.append(self._smoke_load(metadata))

        failed = [check for check in checks if not bool(check.get("passed", False))]
        return {
            "passed": len(failed) == 0,
            "checks": checks,
            "failed_checks": failed,
            "reason": "validation_failed" if failed else "validation_passed",
        }
