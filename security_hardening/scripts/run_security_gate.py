#!/usr/bin/env python
"""Execute security release gate checks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from security_hardening.model_security.secure_loader import SecureLoader
from security_hardening.rollout.security_gate import SecurityGate


def main() -> int:
    parser = argparse.ArgumentParser(description="Run release security gate")
    parser.add_argument("--model-version", required=True)
    parser.add_argument("--robustness-passed", action="store_true")
    parser.add_argument("--robustness-degradation", type=float, default=0.0)
    parser.add_argument("--artifact-integrity-passed", action="store_true")
    parser.add_argument("--extraction-risk-score", type=float, default=0.0)
    parser.add_argument("--extraction-risk-threshold", type=float, default=0.45)
    parser.add_argument("--poisoning-controls-configured", action="store_true")
    parser.add_argument(
        "--blocklist",
        type=Path,
        default=Path("security_hardening/model_security/vulnerable_model_blocklist.yaml"),
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        print(
            json.dumps(
                {
                    "dry_run": True,
                    "model_version": args.model_version,
                    "blocklist": str(args.blocklist),
                },
                indent=2,
            )
        )
        return 0

    blocklisted_versions = SecureLoader.load_blocklist(str(args.blocklist)) if args.blocklist.exists() else set()
    gate = SecurityGate()
    decision = gate.evaluate(
        model_version=args.model_version,
        robustness_passed=args.robustness_passed,
        robustness_degradation=args.robustness_degradation,
        artifact_integrity_passed=args.artifact_integrity_passed,
        blocklisted_versions=blocklisted_versions,
        extraction_risk_score=args.extraction_risk_score,
        extraction_risk_threshold=args.extraction_risk_threshold,
        poisoning_controls_configured=args.poisoning_controls_configured,
    )

    print(
        json.dumps(
            {
                "passed": decision.passed,
                "reasons": decision.reasons,
                "metrics": decision.metrics,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if decision.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
