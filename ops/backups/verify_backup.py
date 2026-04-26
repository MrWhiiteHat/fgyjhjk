"""Backup verification helpers for archive structure and manifest integrity."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Dict, List


def _bytes_sha256(payload: bytes) -> str:
    digest = hashlib.sha256()
    digest.update(payload)
    return digest.hexdigest()


def verify_backup_archive(archive_path: str | Path) -> Dict[str, object]:
    """Verify backup archive readability and manifest checksums."""
    archive_file = Path(archive_path)
    if not archive_file.exists():
        return {"valid": False, "reason": "archive_missing", "archive_path": str(archive_file)}

    errors: List[str] = []
    checked = 0

    try:
        with zipfile.ZipFile(archive_file, "r") as archive:
            bad_member = archive.testzip()
            if bad_member is not None:
                errors.append(f"corrupt_member:{bad_member}")

            if "manifest.json" not in archive.namelist():
                errors.append("manifest_missing")
            else:
                manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
                entries = list(manifest.get("entries", []))
                for entry in entries:
                    member_path = str(entry.get("path", ""))
                    expected_hash = str(entry.get("sha256", ""))
                    if member_path not in archive.namelist():
                        errors.append(f"missing_member:{member_path}")
                        continue
                    content = archive.read(member_path)
                    observed = _bytes_sha256(content)
                    checked += 1
                    if expected_hash and observed != expected_hash:
                        errors.append(f"hash_mismatch:{member_path}")

    except Exception as exc:  # noqa: BLE001
        errors.append(f"archive_read_error:{exc}")

    return {
        "valid": len(errors) == 0,
        "archive_path": str(archive_file.as_posix()),
        "checked_entries": checked,
        "errors": errors,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Verify backup archive integrity")
    parser.add_argument("archive_path", type=str, help="Path to backup zip archive")
    args = parser.parse_args()

    result = verify_backup_archive(args.archive_path)
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result.get("valid", False) else 1)
