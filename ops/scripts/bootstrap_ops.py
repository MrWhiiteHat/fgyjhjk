"""Bootstrap operations directories and baseline state files."""

from __future__ import annotations

import json
from pathlib import Path

from ops.mlops.model_registry import ModelRegistry


REQUIRED_DIRS = [
    "ops/logs",
    "ops/reports",
    "ops/drift/state/references",
    "ops/mlops/state",
    "ops/backups/archives",
    "ops/cost/state",
    "app/backend/outputs/ops",
]


def bootstrap() -> dict:
    created = []
    for directory in REQUIRED_DIRS:
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        created.append(str(path.as_posix()))

    registry = ModelRegistry()
    result = {
        "created_directories": created,
        "model_registry_path": str(registry.registry_path.as_posix()),
    }

    summary_path = Path("ops/reports/bootstrap_summary.json")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")

    result["summary_path"] = str(summary_path.as_posix())
    return result


if __name__ == "__main__":
    payload = bootstrap()
    print(json.dumps(payload, indent=2, sort_keys=True))
