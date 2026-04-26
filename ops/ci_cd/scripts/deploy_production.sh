#!/usr/bin/env bash
set -euo pipefail

MODEL_VERSION="${1:-}"

echo "Deploying to production environment..."
python ops/scripts/run_health_audit.py --output ops/reports/health_audit_production.json

if [[ -n "$MODEL_VERSION" ]]; then
  python ops/scripts/promote_model.py --model-version "$MODEL_VERSION" --target-stage production --actor ci_cd --reason "production deploy workflow"
fi

echo "Production deployment checks completed."
