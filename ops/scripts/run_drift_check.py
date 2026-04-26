"""Run one drift check cycle from a records JSON file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

from ops.monitoring.drift_monitor import DriftMonitor


def _load_records(path: Path) -> List[Dict[str, object]]:
    if not path.exists():
        raise FileNotFoundError(f"Records path not found: {path}")
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
    if path.suffix.lower() == ".jsonl":
        rows = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                item = json.loads(line)
                if isinstance(item, dict):
                    rows.append(item)
        return rows
    raise ValueError("Unsupported records format. Use .json or .jsonl")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run drift check")
    parser.add_argument("--config", default="ops/configs/drift_config.yaml", type=str)
    parser.add_argument("--records", default="ops/drift/state/current_records.json", type=str)
    parser.add_argument("--model-version", default="unknown", type=str)
    parser.add_argument("--reference", default=None, type=str)
    args = parser.parse_args()

    monitor = DriftMonitor(drift_config_path=args.config)
    records_path = Path(args.records)
    if records_path.exists():
        records = _load_records(records_path)
    else:
        records = []

    if not records:
        print(json.dumps({"warning": "no current records found", "records_path": str(records_path.as_posix())}, indent=2))
        return 0

    result = monitor.run_drift_check(
        current_records=records,
        model_version=args.model_version,
        reference_path=args.reference,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
