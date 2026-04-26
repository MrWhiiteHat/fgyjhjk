"""Rollback deployment to specific or previous model version."""

from __future__ import annotations

import argparse
import json

from ops.mlops.rollback_manager import RollbackManager


def main() -> int:
    parser = argparse.ArgumentParser(description="Rollback model deployment")
    parser.add_argument("--target-version", default=None, type=str)
    parser.add_argument("--actor", required=True, type=str)
    parser.add_argument("--reason", required=True, type=str)
    args = parser.parse_args()

    manager = RollbackManager()

    if args.target_version:
        result = manager.rollback_to_version(
            target_version=args.target_version,
            actor=args.actor,
            reason=args.reason,
        )
    else:
        result = manager.rollback_to_previous(
            actor=args.actor,
            reason=args.reason,
        )

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
