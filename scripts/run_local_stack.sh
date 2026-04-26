#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

"$REPO_ROOT/scripts/run_backend.sh" 0.0.0.0 8000 &
BACKEND_PID=$!
"$REPO_ROOT/scripts/run_frontend.sh" 3000 &
FRONTEND_PID=$!

echo "Backend PID:  $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"
echo "Backend:  http://localhost:8000/docs"
echo "Frontend: http://localhost:3000"

tail --pid="$BACKEND_PID" -f /dev/null
