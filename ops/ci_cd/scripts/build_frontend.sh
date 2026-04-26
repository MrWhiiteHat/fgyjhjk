#!/usr/bin/env bash
set -euo pipefail

if [[ ! -d app/frontend ]]; then
  echo "app/frontend not found; skipping frontend build."
  exit 0
fi

pushd app/frontend >/dev/null
if [[ -f package-lock.json ]]; then
  npm ci
else
  npm install
fi
npm run build --if-present
popd >/dev/null

echo "Frontend build completed."
