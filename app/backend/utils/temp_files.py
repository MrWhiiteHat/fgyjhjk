"""Temporary file lifecycle helpers."""

from __future__ import annotations

from dataclasses import dataclass
import time
from pathlib import Path

from app.backend.utils.helpers import ensure_dir
from app.backend.utils.io import cleanup_files_older_than, ensure_safe_path, safe_unlink


@dataclass(frozen=True)
class TempManagerConfig:
    """Runtime settings for temporary upload management."""

    temp_root: Path
    persistent_output_root: Path
    default_cleanup_max_age_seconds: int = 3600


class TempFileManager:
    """Manage temporary files with safe deletion and optional persistence."""

    def __init__(self, config: TempManagerConfig) -> None:
        self.config = config
        self.temp_root = ensure_dir(config.temp_root)
        self.persistent_output_root = ensure_dir(config.persistent_output_root)

    def create_upload_path(self, filename: str, subdir: str = "") -> Path:
        """Create unique upload path under temp root."""
        folder = self.temp_root / subdir if subdir else self.temp_root
        folder = ensure_dir(folder)
        stamp = int(time.time() * 1000)
        return folder / f"{stamp}_{filename}"

    def cleanup_file(self, path: str | Path, preserve: bool = False) -> bool:
        """Delete temporary file unless preserve flag is enabled."""
        if bool(preserve):
            return False
        return safe_unlink(path, self.temp_root)

    def move_to_persistent(self, source_path: str | Path, relative_output_path: str) -> Path:
        """Move temp file to persistent output area for retention workflows."""
        source = ensure_safe_path(source_path, self.temp_root)
        destination = ensure_safe_path(self.persistent_output_root / relative_output_path, self.persistent_output_root)
        destination.parent.mkdir(parents=True, exist_ok=True)
        source.replace(destination)
        return destination

    def cleanup_expired(self, max_age_seconds: int | None = None) -> int:
        """Remove expired files under temp root."""
        age = int(max_age_seconds if max_age_seconds is not None else self.config.default_cleanup_max_age_seconds)
        return cleanup_files_older_than(self.temp_root, max_age_seconds=age)


def create_temp_file_path(temp_dir: str | Path, filename: str) -> Path:
    """Create unique temporary file path for upload handling."""
    manager = TempFileManager(
        TempManagerConfig(
            temp_root=Path(temp_dir),
            persistent_output_root=Path(temp_dir),
            default_cleanup_max_age_seconds=3600,
        )
    )
    return manager.create_upload_path(filename=filename)


def cleanup_old_temp_files(temp_dir: str | Path, max_age_seconds: int) -> int:
    """Delete temporary files older than max_age_seconds and return deletion count."""
    manager = TempFileManager(
        TempManagerConfig(
            temp_root=Path(temp_dir),
            persistent_output_root=Path(temp_dir),
            default_cleanup_max_age_seconds=int(max_age_seconds),
        )
    )
    return manager.cleanup_expired(max_age_seconds=max_age_seconds)
