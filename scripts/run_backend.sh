#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-0.0.0.0}"
PORT="${2:-8000}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [[ ! -x "$REPO_ROOT/.venv/bin/python" ]]; then
  echo "Virtual environment not found at .venv/bin/python. Create it with: python -m venv .venv"
  exit 1
fi

"$REPO_ROOT/.venv/bin/python" -m uvicorn app.backend.main:app --host "$HOST" --port "$PORT"
