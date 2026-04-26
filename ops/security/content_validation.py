"""Content validation utilities for image/video/archive uploads."""

from __future__ import annotations

import mimetypes
import zipfile
from pathlib import Path
from typing import Dict, Iterable, List

from ops.security.input_sanitizer import estimate_archive_depth, normalize_extension, sanitize_filename, validate_archive_member


_ALLOWED_MIME_PREFIX = {
    "image": "image/",
    "video": "video/",
    "archive": "application/zip",
}


def validate_extension(filename: str, allowed_extensions: Iterable[str]) -> str:
    suffix = normalize_extension(filename)
    allowed = {normalize_extension(item) for item in allowed_extensions}
    if suffix not in allowed:
        raise ValueError(f"Unsupported extension '{suffix}'. Allowed={sorted(allowed)}")
    return suffix


def detect_mime_type(path: str | Path) -> str:
    mime, _ = mimetypes.guess_type(str(path))
    return str(mime or "application/octet-stream")


def validate_mime_type(mime_type: str, content_kind: str) -> None:
    kind = str(content_kind).lower()
    if kind == "archive":
        if mime_type not in {"application/zip", "application/octet-stream"}:
            raise ValueError(f"Unsupported archive mime type: {mime_type}")
        return

    prefix = _ALLOWED_MIME_PREFIX.get(kind)
    if prefix is None:
        raise ValueError(f"Unknown content kind: {kind}")
    if not str(mime_type).lower().startswith(prefix):
        raise ValueError(f"Unsupported mime type '{mime_type}' for content kind '{kind}'")


def validate_file_size(path: str | Path, max_size_mb: float) -> int:
    file_path = Path(path)
    size_bytes = file_path.stat().st_size
    max_bytes = int(float(max_size_mb) * 1024 * 1024)
    if size_bytes > max_bytes:
        raise ValueError(f"File exceeds max size. size_bytes={size_bytes} max_bytes={max_bytes}")
    if size_bytes <= 0:
        raise ValueError("Empty file content is not allowed")
    return size_bytes


def validate_image_dimensions(path: str | Path, min_width: int = 16, min_height: int = 16, max_width: int = 8192, max_height: int = 8192) -> Dict[str, int]:
    try:
        from PIL import Image

        with Image.open(path) as img:
            width, height = img.size
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Unreadable image content: {exc}") from exc

    if width < min_width or height < min_height:
        raise ValueError(f"Image dimensions too small: {width}x{height}")
    if width > max_width or height > max_height:
        raise ValueError(f"Image dimensions too large: {width}x{height}")

    return {"width": int(width), "height": int(height)}


def validate_video_dimensions(path: str | Path, min_width: int = 32, min_height: int = 32, max_width: int = 8192, max_height: int = 8192) -> Dict[str, int]:
    try:
        import cv2

        capture = cv2.VideoCapture(str(path))
        if not capture.isOpened():
            raise ValueError("Cannot open video file")
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        capture.release()
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Unreadable video content: {exc}") from exc

    if width <= 0 or height <= 0:
        raise ValueError("Video dimensions unavailable")
    if width < min_width or height < min_height:
        raise ValueError(f"Video dimensions too small: {width}x{height}")
    if width > max_width or height > max_height:
        raise ValueError(f"Video dimensions too large: {width}x{height}")

    return {"width": width, "height": height}


def validate_archive(
    archive_path: str | Path,
    allowed_extensions: Iterable[str],
    max_members: int = 1000,
    max_depth: int = 4,
) -> List[str]:
    """Validate archive members against traversal and nested-depth constraints."""
    allowed = {normalize_extension(ext) for ext in allowed_extensions}
    safe_members: List[str] = []

    with zipfile.ZipFile(archive_path, "r") as archive:
        infos = archive.infolist()
        if len(infos) > max_members:
            raise ValueError(f"Archive has too many members: {len(infos)} > {max_members}")

        for info in infos:
            if info.is_dir():
                continue
            raw_name = info.filename
            _ = validate_archive_member(raw_name)
            if estimate_archive_depth(raw_name) > max_depth:
                raise ValueError(f"Archive member exceeds max nested depth ({max_depth}): {raw_name}")

            sanitized = sanitize_filename(Path(raw_name).name)
            ext = normalize_extension(sanitized)
            if ext not in allowed:
                continue
            safe_members.append(sanitized)

    if not safe_members:
        raise ValueError("Archive did not contain valid allowed files")
    return safe_members
