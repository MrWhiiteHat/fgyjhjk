"""Centralized content limit definitions for API protection."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContentLimits:
    """Upload and request limits for secure endpoint handling."""

    max_image_size_mb: float = 12.0
    max_video_size_mb: float = 300.0
    max_archive_size_mb: float = 350.0
    max_files_per_request: int = 64
    max_total_payload_mb: float = 400.0


def bytes_limit_from_mb(size_mb: float) -> int:
    """Convert MB limit to bytes using binary units."""

    return int(float(size_mb) * 1024 * 1024)


def is_within_bytes_limit(size_bytes: int, limit_mb: float) -> bool:
    """Check if byte size fits within MB limit."""

    return int(size_bytes) <= bytes_limit_from_mb(limit_mb)
