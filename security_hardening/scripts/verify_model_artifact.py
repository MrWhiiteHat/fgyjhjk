#!/usr/bin/env python
"""Verify model artifact integrity and policy compliance."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from security_hardening.model_security.secure_loader import SecureLoader
from security_hardening.model_security.signature_verifier import SignatureVerifier


def _normalize_signature(value: str | None) -> str | None:
    if not value:
        return None
    text = str(value).strip()
    if text.startswith("hmac_sha256:"):
        return text.split(":", 1)[1].strip()
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify model artifact with secure loader")
    parser.add_argument("artifact", type=Path, help="Path to model artifact")
    parser.add_argument("metadata", type=Path, help="Path to metadata json")
    parser.add_argument("--strict", action="store_true", help="Enable strict signature verification")
    parser.add_argument("--blocklist", type=Path, default=None, help="Optional vulnerable version blocklist yaml")
    parser.add_argument("--dry-run", action="store_true", help="Print config and exit")
    args = parser.parse_args()

    if args.dry_run:
        print(
            json.dumps(
                {
                    "dry_run": True,
                    "artifact": str(args.artifact),
                    "metadata": str(args.metadata),
                    "strict": args.strict,
                    "blocklist": str(args.blocklist) if args.blocklist else None,
                },
                indent=2,
            )
        )
        return 0

    metadata = json.loads(args.metadata.read_text(encoding="utf-8"))
    version = str(metadata.get("version", "")).strip()
    expected_sha = str(metadata.get("sha256", "")).strip()
    signature_hex = _normalize_signature(metadata.get("signature"))
    approved_versions = {str(v).strip() for v in (metadata.get("approved_versions") or [version]) if str(v).strip()}
    metadata_blocklisted = {
        str(v).strip() for v in (metadata.get("blocklisted_versions") or []) if str(v).strip()
    }
    file_blocklisted = SecureLoader.load_blocklist(str(args.blocklist)) if args.blocklist and args.blocklist.exists() else set()
    blocklisted_versions = metadata_blocklisted | file_blocklisted

    security_gate_passed = bool(metadata.get("security_gate_passed", True))

    secret = os.getenv("MODEL_SIGNATURE_SECRET", "")
    signature_verifier = SignatureVerifier(secret=secret, enabled=bool(secret))
    loader = SecureLoader(signature_verifier=signature_verifier)
    result = loader.load(
        artifact_path=str(args.artifact),
        expected_sha256=expected_sha,
        model_version=version,
        approved_versions=approved_versions,
        blocklisted_versions=blocklisted_versions,
        security_gate_passed=security_gate_passed,
        strict_mode=args.strict,
        signature_hex=signature_hex,
    )

    print(
        json.dumps(
            {
                "loaded": result.loaded,
                "reason": result.reason,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if result.loaded else 2


if __name__ == "__main__":
    raise SystemExit(main())
