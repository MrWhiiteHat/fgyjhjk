"""Artifact integrity verification using SHA-256 checksums."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from filelock import FileLock


@dataclass
class IntegrityResult:
    """Checksum verification result."""

    valid: bool
    expected_sha256: str
    actual_sha256: str
    reason: str


class ArtifactIntegrityVerifier:
    """Verifies model artifact integrity against expected checksums."""

    def compute_sha256(self, artifact_path: str | Path, chunk_size: int = 65536) -> str:
        """Compute SHA-256 digest for artifact file."""

        path = Path(artifact_path)
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(chunk_size)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()

    def verify(self, *, artifact_path: str | Path, expected_sha256: str) -> IntegrityResult:
        """Verify artifact checksum against expected hash."""

        actual = self.compute_sha256(artifact_path)
        expected = str(expected_sha256).strip().lower()
        valid = actual.lower() == expected
        reason = "ok" if valid else "checksum_mismatch"
        return IntegrityResult(valid=valid, expected_sha256=expected, actual_sha256=actual, reason=reason)

    def verify_manifest(self, *, artifact_path: str | Path, manifest_path: str | Path) -> IntegrityResult:
        """Verify artifact using JSON manifest containing sha256 field."""

        manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        expected = str(manifest.get("sha256", "")).strip()
        if not expected:
            return IntegrityResult(valid=False, expected_sha256="", actual_sha256="", reason="missing_sha256_in_manifest")
        return self.verify(artifact_path=artifact_path, expected_sha256=expected)

    def write_manifest(self, *, artifact_path: str | Path, manifest_path: str | Path) -> dict:
        """Write checksum manifest for artifact with file lock."""

        artifact = Path(artifact_path)
        manifest_file = Path(manifest_path)
        lock_file = manifest_file.with_suffix(manifest_file.suffix + ".lock")
        lock = FileLock(str(lock_file))

        with lock:
            digest = self.compute_sha256(artifact)
            payload = {
                "artifact_path": str(artifact),
                "sha256": digest,
            }
            manifest_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            return payload
