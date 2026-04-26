"""Secure model loader with integrity, signature, and policy checks."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from security_hardening.model_security.artifact_integrity import ArtifactIntegrityVerifier
from security_hardening.model_security.model_policy import ModelPolicy
from security_hardening.model_security.signature_verifier import SignatureVerifier


@dataclass
class SecureLoadResult:
    """Secure loader decision and artifact payload container."""

    loaded: bool
    reason: str
    artifact_bytes: bytes | None = None


class SecureLoader:
    """Loads model artifacts only when policy and integrity checks pass."""

    def __init__(
        self,
        *,
        integrity_verifier: ArtifactIntegrityVerifier | None = None,
        signature_verifier: SignatureVerifier | None = None,
        policy: ModelPolicy | None = None,
    ) -> None:
        self._integrity = integrity_verifier or ArtifactIntegrityVerifier()
        self._signature = signature_verifier or SignatureVerifier(enabled=False)
        self._policy = policy or ModelPolicy()

    def load(
        self,
        *,
        artifact_path: str | Path,
        expected_sha256: str,
        model_version: str,
        approved_versions: set[str],
        blocklisted_versions: set[str],
        security_gate_passed: bool,
        strict_mode: bool = True,
        signature_hex: str | None = None,
    ) -> SecureLoadResult:
        """Securely load artifact bytes when all checks pass."""

        policy_decision = self._policy.evaluate(
            model_version=model_version,
            approved_versions=approved_versions,
            blocklisted_versions=blocklisted_versions,
            security_gate_passed=security_gate_passed,
            strict_mode=strict_mode,
        )
        if not policy_decision.allowed:
            return SecureLoadResult(loaded=False, reason=policy_decision.reason)

        integrity = self._integrity.verify(artifact_path=artifact_path, expected_sha256=expected_sha256)
        if not integrity.valid:
            if strict_mode:
                return SecureLoadResult(loaded=False, reason="artifact_integrity_failure")

        signature = self._signature.verify_file(artifact_path=artifact_path, signature_hex=signature_hex)
        if not signature.verified and strict_mode:
            return SecureLoadResult(loaded=False, reason=f"signature_failure:{signature.reason}")

        payload = Path(artifact_path).read_bytes()
        return SecureLoadResult(loaded=True, reason="ok", artifact_bytes=payload)

    @staticmethod
    def load_blocklist(path: str | Path) -> set[str]:
        """Load vulnerable model blocklist from YAML-like lines or JSON list."""

        raw = Path(path).read_text(encoding="utf-8")
        stripped = raw.strip()

        if stripped.startswith("["):
            values = json.loads(stripped)
            return {str(item).strip() for item in values}

        versions: set[str] = set()
        for line in raw.splitlines():
            text = line.strip()
            if not text or text.startswith("#"):
                continue
            if text.startswith("-"):
                versions.add(text[1:].strip())
            elif ":" in text:
                key, value = text.split(":", 1)
                if key.strip() == "version":
                    versions.add(value.strip())
        return versions
