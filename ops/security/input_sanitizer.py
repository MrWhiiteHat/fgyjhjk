"""Input sanitization utilities for filenames and file-system safety."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path


_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(filename: str, default_name: str = "upload.bin") -> str:
    """Normalize filename and strip dangerous characters."""
    raw = Path(str(filename or "")).name.strip()
    if not raw:
        raw = default_name
    cleaned = _SAFE_NAME_RE.sub("_", raw)
    cleaned = cleaned.strip("._")
    return cleaned or default_name


def normalize_extension(filename: str) -> str:
    """Return normalized lowercase extension with leading dot."""
    suffix = Path(filename).suffix.lower().strip()
    if not suffix:
        return ""
    return suffix if suffix.startswith(".") else f".{suffix}"


def safe_join(base_dir: str | Path, *parts: str) -> Path:
    """Safely join path components and block traversal escapes."""
    base = Path(base_dir).resolve()
    candidate = base.joinpath(*parts).resolve()
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise ValueError("Unsafe path traversal detected") from exc
    return candidate


def validate_archive_member(member_name: str) -> str:
    """Validate archive member path and return safe basename."""
    normalized = member_name.replace("\\", "/")
    if normalized.startswith("/"):
        raise ValueError("Archive member cannot be absolute path")
    if ".." in Path(normalized).parts:
        raise ValueError("Archive member path traversal detected")
    return sanitize_filename(Path(normalized).name)


def estimate_archive_depth(member_name: str) -> int:
    """Estimate nested depth of archive member path."""
    parts = [part for part in member_name.replace("\\", "/").split("/") if part]
    return len(parts)


def file_sha256(path: str | Path, chunk_size: int = 65536) -> str:
    """Compute SHA-256 hash for a file path."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def bytes_sha256(data: bytes) -> str:
    """Compute SHA-256 hash for byte payload."""
    return hashlib.sha256(data).hexdigest()


def reject_dangerous_path(path: str | Path) -> None:
    """Reject obvious dangerous paths, symlinks, and devices."""
    candidate = Path(path)
    if os.name == "nt" and str(candidate).startswith("\\\\.\\"):
        raise ValueError("Device path is not allowed")
    if candidate.exists() and candidate.is_symlink():
        raise ValueError("Symlink paths are not allowed")
