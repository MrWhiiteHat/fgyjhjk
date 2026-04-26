"""Policy-driven backup archive creation with integrity manifest."""

from __future__ import annotations

import hashlib
import json
import time
import zipfile
from pathlib import Path
from typing import Dict, List

import yaml


class BackupManager:
    """Creates backup archives from configured sources and files."""

    def __init__(self, policy_path: str = "ops/backups/backup_policy.yaml") -> None:
        self.policy_path = Path(policy_path)
        self.policy = self._load_policy(self.policy_path)
        self.backup_root = Path(str(self.policy.get("backup_root", "ops/backups/archives")))
        self.backup_root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _now_iso() -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    @staticmethod
    def _timestamp() -> str:
        return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())

    @staticmethod
    def _load_policy(path: Path) -> Dict[str, object]:
        if not path.exists():
            raise FileNotFoundError(f"Backup policy not found: {path}")
        with path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
        if not isinstance(payload, dict):
            raise ValueError("Backup policy must be a mapping")
        return payload

    @staticmethod
    def _file_sha256(path: Path, chunk_size: int = 65536) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(chunk_size)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _to_archive_name(file_path: Path) -> str:
        """Convert absolute file path to stable archive member path."""
        resolved = file_path.resolve()
        cwd = Path.cwd().resolve()
        try:
            return resolved.relative_to(cwd).as_posix()
        except ValueError:
            # Fallback for files outside current workspace root.
            member = resolved.as_posix().replace(":/", "/")
            return member.lstrip("/")

    def _collect_paths(self) -> List[Path]:
        candidates: List[Path] = []

        for source in self.policy.get("sources", []):
            source_path = Path(str(source))
            if not source_path.exists():
                continue
            if source_path.is_file():
                candidates.append(source_path)
            else:
                for item in source_path.rglob("*"):
                    if item.is_file():
                        candidates.append(item)

        for file_path in self.policy.get("include_files", []):
            path = Path(str(file_path))
            if path.exists() and path.is_file():
                candidates.append(path)

        dedup = sorted({path.resolve() for path in candidates})
        return dedup

    def create_backup(self, tier: str = "daily") -> Dict[str, object]:
        archive_name = f"backup_{tier}_{self._timestamp()}.zip"
        archive_path = self.backup_root / archive_name

        files = self._collect_paths()
        manifest_entries = []

        compression_cfg = dict(self.policy.get("compression", {}))
        level = int(compression_cfg.get("level", 6))

        with zipfile.ZipFile(
            archive_path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=level,
        ) as archive:
            for file_path in files:
                arcname = self._to_archive_name(file_path)
                archive.write(file_path, arcname=arcname)
                manifest_entries.append(
                    {
                        "path": arcname,
                        "size_bytes": int(file_path.stat().st_size),
                        "sha256": self._file_sha256(file_path),
                    }
                )

            manifest = {
                "created_at": self._now_iso(),
                "tier": tier,
                "file_count": len(manifest_entries),
                "entries": manifest_entries,
            }
            archive.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True))

        result = {
            "archive_path": str(archive_path.as_posix()),
            "created_at": self._now_iso(),
            "tier": tier,
            "file_count": len(manifest_entries),
            "size_bytes": int(archive_path.stat().st_size),
        }

        if bool(dict(self.policy.get("integrity", {})).get("verify_on_create", True)):
            from ops.backups.verify_backup import verify_backup_archive

            verification = verify_backup_archive(archive_path)
            result["verification"] = verification
            if not verification.get("valid", False):
                raise RuntimeError(f"Backup verification failed: {verification}")

        self._apply_retention()
        return result

    def _apply_retention(self) -> None:
        retention_cfg = dict(self.policy.get("retention", {}))
        tier_limits = {
            "daily": int(retention_cfg.get("keep_daily", 7)),
            "weekly": int(retention_cfg.get("keep_weekly", 4)),
            "monthly": int(retention_cfg.get("keep_monthly", 6)),
        }

        archives = sorted(self.backup_root.glob("backup_*.zip"))
        for tier, keep_count in tier_limits.items():
            tier_archives = [item for item in archives if f"backup_{tier}_" in item.name]
            excess = max(0, len(tier_archives) - max(0, keep_count))
            for old in tier_archives[:excess]:
                old.unlink(missing_ok=True)
