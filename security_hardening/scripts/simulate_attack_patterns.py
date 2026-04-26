#!/usr/bin/env python
"""Simulate extraction attack query patterns for detector validation."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from security_hardening.extraction.query_pattern_detector import QueryPatternDetector, QueryRecord


def _build_queries(pattern: str, count: int) -> list[QueryRecord]:
    now = datetime.now(tz=timezone.utc)
    queries: list[QueryRecord] = []
    for idx in range(count):
        timestamp = (now - timedelta(seconds=idx)).isoformat()
        if pattern == "tiny_mod":
            queries.append(
                QueryRecord(
                    timestamp=timestamp,
                    input_digest=f"aaaaaaaaaaaaaaa{idx % 2}",
                    confidence=max(0.5, 0.9 - idx * 0.002),
                    threshold=0.5,
                )
            )
        elif pattern == "threshold":
            conf = 0.49 if idx % 2 == 0 else 0.51
            queries.append(
                QueryRecord(
                    timestamp=timestamp,
                    input_digest=f"{idx:032x}",
                    confidence=conf,
                    threshold=0.45 + (idx % 8) * 0.02,
                )
            )
        else:
            queries.append(
                QueryRecord(
                    timestamp=timestamp,
                    input_digest=f"{idx:032x}",
                    confidence=0.5,
                    threshold=0.5,
                )
            )
    return queries


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulate extraction attack patterns")
    parser.add_argument("--pattern", choices=["bulk", "tiny_mod", "threshold"], default="bulk")
    parser.add_argument("--count", type=int, default=80)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        print(json.dumps({"dry_run": True, "pattern": args.pattern, "count": args.count}, indent=2))
        return 0

    detector = QueryPatternDetector()
    queries = _build_queries(args.pattern, args.count)
    result = detector.analyze(history=queries)

    print(
        json.dumps(
            {
                "pattern": args.pattern,
                "count": args.count,
                "risk_score": result.risk_score,
                "suspicious": result.suspicious,
                "reason_codes": result.reason_codes,
                "metadata": result.metadata,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
