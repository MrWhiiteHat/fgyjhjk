"""General helper utilities used across backend modules."""

from __future__ import annotations

import hashlib
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


def now_utc_iso() -> str:
    """Return current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


def generate_request_id() -> str:
    """Generate a random request identifier."""
    return str(uuid.uuid4())


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """Sanitize untrusted filename to safe filesystem-friendly name."""
    raw = str(filename or "").strip().replace("\\", "/")
    leaf = raw.split("/")[-1]
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", leaf)
    safe = re.sub(r"_+", "_", safe).strip("._")
    if not safe:
        safe = "upload"
    return safe[:max_length]


def ensure_dir(path: str | Path) -> Path:
    """Create directory if missing and return normalized path."""
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    return target


def hash_bytes(data: bytes) -> str:
    """Compute SHA256 hash for in-memory bytes."""
    return hashlib.sha256(data).hexdigest()


def hash_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    """Compute SHA256 hash for file contents."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def normalize_extension(ext: str) -> str:
    """Normalize file extension to lowercase dot-prefixed string."""
    raw = str(ext).strip().lower()
    if not raw:
        return ""
    return raw if raw.startswith(".") else f".{raw}"


def total_size_bytes(paths: Iterable[str | Path]) -> int:
    """Compute combined file size for iterable of paths."""
    total = 0
    for path in paths:
        target = Path(path)
        if target.exists() and target.is_file():
            total += target.stat().st_size
    return total


def is_truthy(value: str | None) -> bool:
    """Convert textual env-like values to bool."""
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def relative_to(path: str | Path, root: str | Path) -> str:
    """Return relative POSIX path when possible, else absolute POSIX path."""
    target = Path(path)
    base = Path(root)
    try:
        return str(target.resolve().relative_to(base.resolve()).as_posix())
    except Exception:
        return str(target.as_posix())


def safe_remove(path: str | Path) -> None:
    """Remove file if it exists without raising for missing files."""
    target = Path(path)
    if target.exists() and target.is_file():
        target.unlink(missing_ok=True)


def env_or_default(name: str, default: str) -> str:
    """Read environment variable with fallback."""
    return os.environ.get(name, default)
