"""CLI wrapper for backup manager."""

from __future__ import annotations

import argparse
import json

from ops.backups.backup_manager import BackupManager


def main() -> int:
    parser = argparse.ArgumentParser(description="Run backup creation")
    parser.add_argument("--policy", default="ops/backups/backup_policy.yaml", type=str)
    parser.add_argument("--tier", default="daily", choices=["daily", "weekly", "monthly"])
    args = parser.parse_args()

    manager = BackupManager(policy_path=args.policy)
    result = manager.create_backup(tier=args.tier)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
