#!/usr/bin/env bash
set -euo pipefail

echo "Deploying to staging environment..."
python ops/scripts/run_health_audit.py --output ops/reports/health_audit_staging.json

echo "Staging deployment checks completed."
