from __future__ import annotations

import hashlib
import hmac
from pathlib import Path

from security_hardening.model_security.secure_loader import SecureLoader
from security_hardening.model_security.signature_verifier import SignatureVerifier


def _write_artifact(path: Path, data: bytes) -> str:
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def test_secure_loader_allows_valid_artifact(tmp_path: Path) -> None:
    artifact = tmp_path / "model.bin"
    checksum = _write_artifact(artifact, b"safe_model_payload")

    loader = SecureLoader()
    result = loader.load(
        artifact_path=str(artifact),
        expected_sha256=checksum,
        model_version="1.2.3",
        approved_versions={"1.2.3"},
        blocklisted_versions={"9.9.9"},
        security_gate_passed=True,
        strict_mode=False,
    )

    assert result.loaded is True
    assert result.reason == "ok"


def test_secure_loader_blocks_checksum_mismatch(tmp_path: Path) -> None:
    artifact = tmp_path / "model.bin"
    _write_artifact(artifact, b"safe_model_payload")

    loader = SecureLoader()
    result = loader.load(
        artifact_path=str(artifact),
        expected_sha256="deadbeef",
        model_version="1.0.0",
        approved_versions={"1.0.0"},
        blocklisted_versions=set(),
        security_gate_passed=True,
        strict_mode=True,
    )

    assert result.loaded is False
    assert result.reason == "artifact_integrity_failure"


def test_secure_loader_blocks_blocklisted_version(tmp_path: Path) -> None:
    artifact = tmp_path / "model.bin"
    checksum = _write_artifact(artifact, b"safe_model_payload")

    loader = SecureLoader()
    result = loader.load(
        artifact_path=str(artifact),
        expected_sha256=checksum,
        model_version="1.0.1",
        approved_versions={"1.0.1"},
        blocklisted_versions={"1.0.1"},
        security_gate_passed=True,
        strict_mode=True,
    )

    assert result.loaded is False
    assert result.reason == "model_blocklisted"


def test_secure_loader_signature_strict_mode(tmp_path: Path, monkeypatch) -> None:
    artifact = tmp_path / "model.bin"
    payload = b"signed_model_payload"
    checksum = _write_artifact(artifact, payload)

    secret = "integration-secret"
    monkeypatch.setenv("MODEL_SIGNATURE_SECRET", secret)

    signature_hex = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    verifier = SignatureVerifier(secret=secret, enabled=True)
    loader = SecureLoader(signature_verifier=verifier)
    result = loader.load(
        artifact_path=str(artifact),
        expected_sha256=checksum,
        model_version="1.1.0",
        approved_versions={"1.1.0"},
        blocklisted_versions=set(),
        security_gate_passed=True,
        strict_mode=True,
        signature_hex=signature_hex,
    )

    assert result.loaded is True
