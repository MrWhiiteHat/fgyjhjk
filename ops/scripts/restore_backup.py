"""CLI wrapper for safe backup restore."""

from __future__ import annotations

import argparse
import json

from ops.backups.restore_manager import RestoreManager


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore backup archive")
    parser.add_argument("--archive", required=True, type=str)
    parser.add_argument("--restore-root", default="ops/backups/restore", type=str)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    manager = RestoreManager(default_restore_root=args.restore_root)
    result = manager.restore(archive_path=args.archive, restore_root=args.restore_root, overwrite=args.overwrite)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
