"""Promote model version between lifecycle stages."""

from __future__ import annotations

import argparse
import json

from ops.mlops.model_promotion import ModelPromotionService


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote model version")
    parser.add_argument("--model-version", required=True, type=str)
    parser.add_argument("--target-stage", required=True, choices=["staging", "production", "archived"])
    parser.add_argument("--actor", required=True, type=str)
    parser.add_argument("--reason", required=True, type=str)
    parser.add_argument("--approval-token", default=None, type=str)
    args = parser.parse_args()

    service = ModelPromotionService()
    result = service.promote(
        model_version=args.model_version,
        target_stage=args.target_stage,
        actor=args.actor,
        reason=args.reason,
        approval_token=args.approval_token,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
