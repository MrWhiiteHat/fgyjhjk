"""Input validation helpers for uploads and archive extraction safety."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from app.backend.core.exceptions import FileTooLargeError, UnsupportedFileTypeError, ValidationError
from app.backend.utils.helpers import normalize_extension


def ensure_non_empty_bytes(data: bytes, context: str = "upload") -> None:
    """Reject empty upload payloads."""
    if not data:
        raise ValidationError(f"Empty {context} payload is not allowed")


def ensure_allowed_extension(filename: str, allowed_extensions: Iterable[str]) -> str:
    """Validate filename extension against allow-list."""
    suffix = normalize_extension(Path(filename).suffix)
    allowed = {normalize_extension(ext) for ext in allowed_extensions}
    if suffix not in allowed:
        raise UnsupportedFileTypeError(
            message=f"Unsupported file extension '{suffix}'",
            details={"allowed_extensions": sorted(allowed)},
        )
    return suffix


def ensure_max_size(file_size_bytes: int, max_size_mb: float, context: str = "file") -> None:
    """Validate maximum file size in bytes."""
    limit_bytes = int(float(max_size_mb) * 1024.0 * 1024.0)
    if int(file_size_bytes) > limit_bytes:
        raise FileTooLargeError(
            message=f"{context} exceeds maximum size limit",
            details={"size_bytes": int(file_size_bytes), "max_size_bytes": int(limit_bytes)},
        )


def ensure_safe_archive_member(member_name: str) -> None:
    """Reject path traversal and absolute paths in archive members."""
    normalized = member_name.replace("\\", "/")
    if normalized.startswith("/"):
        raise ValidationError("Archive member path cannot be absolute")
    if ".." in Path(normalized).parts:
        raise ValidationError("Archive member path traversal detected")
