"""File IO helpers for backend API services."""

from __future__ import annotations

import time
import shutil
from pathlib import Path
from typing import Iterable, Tuple


def ensure_dirs(paths: Iterable[str | Path]) -> list[Path]:
    """Create multiple directories and return normalized paths."""
    created: list[Path] = []
    for path in paths:
        target = Path(path)
        target.mkdir(parents=True, exist_ok=True)
        created.append(target)
    return created


def resolve_path(path: str | Path) -> Path:
    """Resolve path to absolute form without requiring existence."""
    return Path(path).expanduser().resolve(strict=False)


def is_within_directory(path: str | Path, root: str | Path) -> bool:
    """Return True when path is located under root directory."""
    target = resolve_path(path)
    parent = resolve_path(root)
    try:
        target.relative_to(parent)
        return True
    except Exception:
        return False


def ensure_safe_path(path: str | Path, allowed_root: str | Path) -> Path:
    """Validate that path stays within allowed root and return resolved path."""
    target = resolve_path(path)
    if not is_within_directory(target, allowed_root):
        raise ValueError(f"Unsafe path outside allowed root: {target}")
    return target


def file_size_bytes(path: str | Path) -> int:
    """Return file size in bytes."""
    target = Path(path)
    if not target.exists() or not target.is_file():
        return 0
    return int(target.stat().st_size)


def file_size_mb(path: str | Path) -> float:
    """Return file size in MB."""
    return file_size_bytes(path) / (1024.0 * 1024.0)


def copy_file(src: str | Path, dst: str | Path, overwrite: bool = True) -> Tuple[bool, str]:
    """Copy file with optional overwrite behavior."""
    source = Path(src)
    destination = Path(dst)
    if not source.exists() or not source.is_file():
        return False, f"Source file not found: {source}"

    if destination.exists() and not overwrite:
        return False, f"Destination file already exists: {destination}"

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return True, ""


def write_text(path: str | Path, content: str) -> Path:
    """Write text content to file."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        handle.write(content)
    return target


def safe_unlink(path: str | Path, allowed_root: str | Path) -> bool:
    """Delete file only when path is inside allowed root."""
    target = ensure_safe_path(path, allowed_root)
    if target.exists() and target.is_file():
        target.unlink(missing_ok=True)
        return True
    return False


def safe_rmtree(path: str | Path, allowed_root: str | Path) -> int:
    """Delete directory tree only when inside allowed root and return removed file count."""
    target = ensure_safe_path(path, allowed_root)
    if not target.exists() or not target.is_dir():
        return 0

    removed_files = sum(1 for item in target.rglob("*") if item.is_file())
    shutil.rmtree(target, ignore_errors=True)
    return removed_files


def cleanup_files_older_than(root: str | Path, max_age_seconds: int) -> int:
    """Remove files older than max age under root and return deletion count."""
    if int(max_age_seconds) < 0:
        raise ValueError("max_age_seconds must be >= 0")

    folder = resolve_path(root)
    if not folder.exists() or not folder.is_dir():
        return 0

    now = time.time()
    removed = 0

    for path in folder.rglob("*"):
        if not path.is_file():
            continue
        age = now - path.stat().st_mtime
        if age >= int(max_age_seconds):
            safe_unlink(path, folder)
            removed += 1

    return removed
