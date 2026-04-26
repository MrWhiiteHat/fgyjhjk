#!/usr/bin/env bash
set -euo pipefail

python -m pip install --upgrade pip
if [[ -f requirements.txt ]]; then
  python -m pip install -r requirements.txt
fi

echo "Backend build/dependency preparation completed."
