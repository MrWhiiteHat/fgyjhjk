#!/usr/bin/env bash
set -euo pipefail

PORT="${1:-3000}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT/app/frontend"

if [[ ! -d node_modules ]]; then
  npm install
fi

if [[ "$PORT" == "3000" ]]; then
  npm run dev
else
  npx next dev -p "$PORT"
fi
