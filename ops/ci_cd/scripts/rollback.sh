#!/usr/bin/env bash
set -euo pipefail

TARGET_VERSION="${1:-}"
if [[ -z "$TARGET_VERSION" ]]; then
  echo "Usage: rollback.sh <model_version>"
  exit 1
fi

python ops/scripts/rollback_deployment.py --target-version "$TARGET_VERSION" --actor ci_cd --reason "manual rollback script"
