"""Filesystem-backed artifact store with checksums and safe copy/move helpers."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Dict, List

from ops.mlops.model_metadata import ModelMetadata


class ArtifactStore:
    """Local artifact store for model and operations artifacts."""

    def __init__(self, root_path: str = "ops/mlops/state/artifacts") -> None:
        self.root_path = Path(root_path)
        self.root_path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _normalize_type(artifact_type: str) -> str:
        mapping = {
            "checkpoint": "checkpoints",
            "checkpoints": "checkpoints",
            "exported_model": "exported_models",
            "exported_models": "exported_models",
            "evaluation_report": "evaluation_reports",
            "evaluation_reports": "evaluation_reports",
            "drift_report": "drift_reports",
            "drift_reports": "drift_reports",
            "model_card": "model_cards",
            "model_cards": "model_cards",
        }
        normalized = mapping.get(str(artifact_type).lower())
        if normalized is None:
            raise ValueError(f"Unsupported artifact type: {artifact_type}")
        return normalized

    def _target_path(self, artifact_type: str, model_version: str, source_path: str | Path) -> Path:
        folder = self._normalize_type(artifact_type)
        destination_dir = self.root_path / folder / str(model_version)
        destination_dir.mkdir(parents=True, exist_ok=True)
        filename = Path(source_path).name
        return destination_dir / filename

    def store_artifact(
        self,
        source_path: str | Path,
        artifact_type: str,
        model_version: str,
        move: bool = False,
    ) -> Dict[str, object]:
        """Store artifact under versioned path with checksum metadata."""
        source = Path(source_path)
        if not source.exists() or not source.is_file():
            raise FileNotFoundError(f"Artifact source does not exist: {source}")

        target = self._target_path(artifact_type=artifact_type, model_version=model_version, source_path=source)
        if move:
            shutil.move(str(source), str(target))
        else:
            shutil.copy2(str(source), str(target))

        checksum = ModelMetadata.compute_file_hash(target)
        metadata = {
            "artifact_type": self._normalize_type(artifact_type),
            "model_version": str(model_version),
            "source_path": str(source.as_posix()),
            "stored_path": str(target.as_posix()),
            "checksum": checksum,
            "size_bytes": int(target.stat().st_size),
        }

        metadata_path = target.with_suffix(target.suffix + ".meta.json")
        metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")

        return metadata

    def verify_artifact(self, stored_path: str | Path, expected_checksum: str) -> bool:
        path = Path(stored_path)
        if not path.exists() or not path.is_file():
            return False
        current = ModelMetadata.compute_file_hash(path)
        return current == str(expected_checksum)

    def ensure_exists(self, stored_path: str | Path) -> Path:
        path = Path(stored_path)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Stored artifact missing: {path}")
        return path

    def list_artifacts(self, model_version: str | None = None) -> List[Dict[str, object]]:
        results: List[Dict[str, object]] = []
        for meta_file in self.root_path.rglob("*.meta.json"):
            try:
                payload = json.loads(meta_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if model_version is not None and str(payload.get("model_version", "")) != str(model_version):
                continue
            results.append(payload)
        return sorted(results, key=lambda item: str(item.get("stored_path", "")))
