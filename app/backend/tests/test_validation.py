"""Unit tests for validation helper functions and exception contracts."""

from __future__ import annotations

import pytest

from app.backend.core.exceptions import FileTooLargeError, UnsupportedFileTypeError, ValidationError
from app.backend.core.validation import ensure_allowed_extension, ensure_max_size, ensure_non_empty_bytes, ensure_safe_archive_member


def test_ensure_allowed_extension_accepts_valid_suffix() -> None:
    suffix = ensure_allowed_extension("sample.JPG", [".jpg", ".png"])
    assert suffix == ".jpg"


def test_ensure_allowed_extension_rejects_invalid_suffix() -> None:
    with pytest.raises(UnsupportedFileTypeError):
        ensure_allowed_extension("sample.gif", [".jpg", ".png"])


def test_ensure_max_size_raises_for_oversized_payload() -> None:
    with pytest.raises(FileTooLargeError):
        ensure_max_size(file_size_bytes=3 * 1024 * 1024, max_size_mb=1.0, context="upload")


def test_ensure_non_empty_bytes_raises_on_empty_payload() -> None:
    with pytest.raises(ValidationError):
        ensure_non_empty_bytes(b"", context="image")


def test_ensure_safe_archive_member_rejects_path_traversal() -> None:
    with pytest.raises(ValidationError):
        ensure_safe_archive_member("../evil.jpg")


def test_ensure_safe_archive_member_accepts_normal_path() -> None:
    ensure_safe_archive_member("nested/image.png")
