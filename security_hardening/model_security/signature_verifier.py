"""Optional signature verification for model artifacts."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SignatureVerificationResult:
    """Signature verification output."""

    verified: bool
    reason: str


class SignatureVerifier:
    """Verifies artifact signatures using shared-secret HMAC policy."""

    def __init__(self, secret: str | None = None, enabled: bool = False) -> None:
        self._secret = str(secret or "")
        self._enabled = bool(enabled)

    def is_enabled(self) -> bool:
        """Return signature verification enablement state."""

        return self._enabled and bool(self._secret)

    def sign_file(self, *, artifact_path: str | Path) -> str:
        """Generate HMAC-SHA256 signature for artifact bytes."""

        if not self.is_enabled():
            raise ValueError("Signature verifier is not enabled")

        payload = Path(artifact_path).read_bytes()
        return hmac.new(self._secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()

    def verify_file(self, *, artifact_path: str | Path, signature_hex: str | None) -> SignatureVerificationResult:
        """Verify artifact signature when enabled, else return skipped status."""

        if not self.is_enabled():
            return SignatureVerificationResult(verified=True, reason="signature_verification_disabled")

        if not signature_hex:
            return SignatureVerificationResult(verified=False, reason="missing_signature")

        expected = self.sign_file(artifact_path=artifact_path)
        provided = str(signature_hex).strip().lower()
        ok = hmac.compare_digest(expected, provided)
        return SignatureVerificationResult(verified=ok, reason="ok" if ok else "signature_mismatch")
