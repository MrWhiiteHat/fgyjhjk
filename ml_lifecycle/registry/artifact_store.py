"""Local artifact storage and manifest tracking for model versions."""

from __future__ import annotations

import json
from pathlib import Path


class ArtifactStore:
    """Stores model artifacts and metadata manifests in local filesystem."""

    def __init__(self, root_dir: Path | str = "ml_lifecycle/artifacts") -> None:
        self._root = Path(root_dir)
        self._root.mkdir(parents=True, exist_ok=True)

    def put_artifact(self, model_version: str, payload: bytes, metadata: dict | None = None) -> str:
        """Persist artifact payload for model version and return artifact URI."""

        version_dir = self._root / model_version
        version_dir.mkdir(parents=True, exist_ok=True)

        artifact_path = version_dir / "model.bin"
        artifact_path.write_bytes(payload)

        manifest = {
            "model_version": model_version,
            "artifact_path": str(artifact_path),
            "metadata": dict(metadata or {}),
        }
        manifest_path = version_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        return str(artifact_path)

    def put_artifact_from_path(self, model_version: str, source_path: Path | str, metadata: dict | None = None) -> str:
        """Copy artifact bytes from existing file path and store as version artifact."""

        source = Path(source_path)
        payload = source.read_bytes()
        merged_metadata = dict(metadata or {})
        merged_metadata["source_path"] = str(source)
        return self.put_artifact(model_version=model_version, payload=payload, metadata=merged_metadata)

    def get_manifest(self, model_version: str) -> dict:
        """Read manifest for a model version."""

        manifest_path = self._root / model_version / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found for version {model_version}")
        return json.loads(manifest_path.read_text(encoding="utf-8"))
