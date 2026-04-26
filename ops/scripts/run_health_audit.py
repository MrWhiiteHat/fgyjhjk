"""Run one health-monitor snapshot and write audit report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ops.monitoring.health_monitor import HealthMonitor


def main() -> int:
    parser = argparse.ArgumentParser(description="Run health audit")
    parser.add_argument("--config", default="ops/configs/monitoring_config.yaml", type=str)
    parser.add_argument("--output", default="ops/reports/health_audit.json", type=str)
    args = parser.parse_args()

    monitor = HealthMonitor(monitoring_config_path=args.config)
    snapshot = monitor.run_once()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(snapshot.to_dict(), indent=2, sort_keys=True), encoding="utf-8")

    print(json.dumps({"output": str(output_path.as_posix()), "state": snapshot.state}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
