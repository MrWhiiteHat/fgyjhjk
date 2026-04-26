"""Safe restore manager for backup archives."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Dict, List


class RestoreManager:
    """Restores files from backup archives with path traversal protection."""

    def __init__(self, default_restore_root: str = "ops/backups/restore") -> None:
        self.default_restore_root = Path(default_restore_root)
        self.default_restore_root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _safe_extract_member(root: Path, member_name: str) -> Path:
        target = (root / member_name).resolve()
        try:
            target.relative_to(root.resolve())
        except ValueError as exc:
            raise ValueError(f"Unsafe archive member path: {member_name}") from exc
        return target

    def list_archive_contents(self, archive_path: str | Path) -> List[str]:
        with zipfile.ZipFile(archive_path, "r") as archive:
            return archive.namelist()

    def restore(
        self,
        archive_path: str | Path,
        restore_root: str | Path | None = None,
        overwrite: bool = False,
    ) -> Dict[str, object]:
        archive_file = Path(archive_path)
        if not archive_file.exists():
            raise FileNotFoundError(f"Archive not found: {archive_file}")

        target_root = Path(restore_root) if restore_root else self.default_restore_root
        target_root.mkdir(parents=True, exist_ok=True)

        restored_files: List[str] = []
        with zipfile.ZipFile(archive_file, "r") as archive:
            for member in archive.infolist():
                if member.is_dir():
                    continue
                target = self._safe_extract_member(target_root, member.filename)
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists() and not overwrite:
                    continue
                with archive.open(member, "r") as src, target.open("wb") as dst:
                    dst.write(src.read())
                restored_files.append(str(target.as_posix()))

        return {
            "archive_path": str(archive_file.as_posix()),
            "restore_root": str(target_root.as_posix()),
            "restored_files": restored_files,
            "restored_count": len(restored_files),
        }
