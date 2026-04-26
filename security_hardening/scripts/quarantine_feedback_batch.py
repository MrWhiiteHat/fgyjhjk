#!/usr/bin/env python
"""Sanitize feedback batch and split cleaned vs quarantined outputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from security_hardening.poisoning.feedback_sanitizer import FeedbackSanitizer


def _load_feedback(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []

    if text.startswith("["):
        payload = json.loads(text)
        if not isinstance(payload, list):
            raise ValueError("JSON payload must be list")
        return [dict(item) for item in payload]

    lines = [line for line in text.splitlines() if line.strip()]
    return [json.loads(line) for line in lines]


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Quarantine suspicious feedback batch")
    parser.add_argument("input", type=Path, help="Feedback JSON or JSONL file")
    parser.add_argument("--cleaned-out", type=Path, default=Path("security_hardening/tmp/feedback_cleaned.json"))
    parser.add_argument(
        "--quarantine-out",
        type=Path,
        default=Path("security_hardening/tmp/feedback_quarantined.json"),
    )
    parser.add_argument("--policy", type=Path, default=None, help="Optional sanitizer policy JSON file")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        print(
            json.dumps(
                {
                    "dry_run": True,
                    "input": str(args.input),
                    "cleaned_out": str(args.cleaned_out),
                    "quarantine_out": str(args.quarantine_out),
                    "policy": str(args.policy) if args.policy else None,
                },
                indent=2,
            )
        )
        return 0

    feedback = _load_feedback(args.input)
    policy = {}
    if args.policy is not None and args.policy.exists():
        policy = json.loads(args.policy.read_text(encoding="utf-8"))

    sanitizer = FeedbackSanitizer()
    result = sanitizer.sanitize(feedback_records=feedback, policy=policy)

    _write_json(args.cleaned_out, result.accepted_records)
    _write_json(args.quarantine_out, result.quarantined_records)

    print(
        json.dumps(
            {
                "total": len(feedback),
                "cleaned": len(result.accepted_records),
                "quarantined": len(result.quarantined_records),
                "quarantine_ratio": result.stats.get("quarantine_rate", 0.0),
                "suspect_reasons": result.reasons_by_feedback_id,
                "cleaned_out": str(args.cleaned_out),
                "quarantine_out": str(args.quarantine_out),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
