"""Safe file upload handling, validation, and archive extraction service."""

from __future__ import annotations

import mimetypes
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

from fastapi import UploadFile

from app.backend.config import get_settings
from app.backend.core.exceptions import ValidationError
from app.backend.core.validation import (
    ensure_allowed_extension,
    ensure_max_size,
    ensure_non_empty_bytes,
    ensure_safe_archive_member,
)
from app.backend.utils.helpers import hash_bytes, sanitize_filename
from app.backend.utils.logger import configure_logger
from app.backend.utils.temp_files import TempFileManager, TempManagerConfig


GENERIC_BINARY_CONTENT_TYPES = {
    "",
    "application/octet-stream",
    "binary/octet-stream",
    "application/x-binary",
}


def _guess_content_type(filename: str, expected_prefix: str | None) -> str:
    """Infer a stable MIME type from filename with safe prefix fallback."""
    guessed, _ = mimetypes.guess_type(filename)
    if guessed:
        return str(guessed).lower()

    if expected_prefix == "image/":
        return "image/unknown"
    if expected_prefix == "video/":
        return "video/unknown"
    return "application/octet-stream"


@dataclass
class SavedUpload:
    """Container for validated upload saved to local filesystem."""

    original_filename: str
    safe_filename: str
    saved_path: Path
    size_bytes: int
    content_type: str
    sha256: str


class FileService:
    """File service handling secure upload save, extraction, and cleanup."""

    _instance: "FileService | None" = None

    def __init__(self) -> None:
        self.settings = get_settings()
        self.logger = configure_logger("backend.file_service", self.settings.LOG_LEVEL, f"{self.settings.OUTPUT_DIR}/logs")
        self.temp_manager = TempFileManager(
            TempManagerConfig(
                temp_root=Path(self.settings.TEMP_DIR),
                persistent_output_root=Path(self.settings.OUTPUT_DIR),
                default_cleanup_max_age_seconds=int(self.settings.TEMP_MAX_AGE_SECONDS),
            )
        )

    @classmethod
    def get_instance(cls) -> "FileService":
        """Get singleton file service instance."""
        if cls._instance is None:
            cls._instance = FileService()
        return cls._instance

    async def save_image_upload(self, upload: UploadFile) -> SavedUpload:
        """Validate and save image upload to temporary path."""
        return await self._save_upload(
            upload=upload,
            allowed_extensions=self.settings.ALLOWED_IMAGE_EXTENSIONS,
            max_size_mb=float(self.settings.MAX_IMAGE_SIZE_MB),
            subdir="images",
            expected_content_prefix="image/",
        )

    async def save_video_upload(self, upload: UploadFile) -> SavedUpload:
        """Validate and save video upload to temporary path."""
        return await self._save_upload(
            upload=upload,
            allowed_extensions=self.settings.ALLOWED_VIDEO_EXTENSIONS,
            max_size_mb=float(self.settings.MAX_VIDEO_SIZE_MB),
            subdir="videos",
            expected_content_prefix="video/",
        )

    async def save_archive_upload(self, upload: UploadFile) -> SavedUpload:
        """Validate and save archive upload (ZIP only)."""
        return await self._save_upload(
            upload=upload,
            allowed_extensions=[".zip"],
            max_size_mb=float(self.settings.MAX_VIDEO_SIZE_MB),
            subdir="archives",
            expected_content_prefix=None,
        )

    async def _save_upload(
        self,
        upload: UploadFile,
        allowed_extensions: Iterable[str],
        max_size_mb: float,
        subdir: str,
        expected_content_prefix: str | None,
    ) -> SavedUpload:
        """Read upload, validate content, and persist to unique temporary path."""
        original_name = upload.filename or "upload.bin"
        safe_name = sanitize_filename(original_name)
        content_type = str(upload.content_type or "").strip().lower()

        if expected_content_prefix:
            is_expected_prefix = content_type.startswith(expected_content_prefix)
            is_generic_binary = content_type in GENERIC_BINARY_CONTENT_TYPES
            if not is_expected_prefix and not is_generic_binary:
                raise ValidationError(
                    "Invalid upload content type",
                    details={
                        "expected_prefix": expected_content_prefix,
                        "received": content_type or "unknown",
                    },
                )
        elif subdir == "archives" and content_type not in {
            "application/zip",
            "application/x-zip-compressed",
            "multipart/x-zip",
            "application/octet-stream",
            "",
        }:
            raise ValidationError(
                "Invalid archive content type",
                details={"received": content_type},
            )

        ensure_allowed_extension(safe_name, allowed_extensions)

        if expected_content_prefix and content_type in GENERIC_BINARY_CONTENT_TYPES:
            # Some browsers/clients send generic binary MIME types for valid media files.
            content_type = _guess_content_type(safe_name, expected_content_prefix)

        data = await upload.read()
        ensure_non_empty_bytes(data, context=safe_name)
        ensure_max_size(len(data), max_size_mb=max_size_mb, context=safe_name)
        self.logger.info(
            "stage=file_validated filename=%s size_bytes=%d content_type=%s",
            safe_name,
            len(data),
            content_type or "application/octet-stream",
        )

        target_path = self.temp_manager.create_upload_path(filename=safe_name, subdir=subdir)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with target_path.open("wb") as handle:
                handle.write(data)
        except Exception as exc:
            self.temp_manager.cleanup_file(target_path, preserve=bool(self.settings.PRESERVE_FAILED_UPLOADS))
            raise ValidationError("Failed to persist uploaded file", details={"cause": str(exc)}) from exc

        digest = hash_bytes(data)
        self.logger.info("stage=file_saved path=%s", str(target_path.as_posix()))

        return SavedUpload(
            original_filename=original_name,
            safe_filename=safe_name,
            saved_path=target_path,
            size_bytes=len(data),
            content_type=content_type or _guess_content_type(safe_name, expected_content_prefix),
            sha256=digest,
        )

    def extract_zip_archive(self, archive_path: str | Path, destination_subdir: str = "archives_extracted") -> List[Path]:
        """Extract ZIP archive safely with path traversal protection."""
        archive = Path(archive_path)
        if not archive.exists() or not archive.is_file():
            raise ValidationError(f"Archive file does not exist: {archive}")

        output_dir = Path(self.settings.TEMP_DIR) / destination_subdir / archive.stem
        if output_dir.exists() and output_dir.is_dir():
            shutil.rmtree(output_dir, ignore_errors=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        extracted: List[Path] = []
        with zipfile.ZipFile(archive, "r") as zf:
            for member in zf.infolist():
                ensure_safe_archive_member(member.filename)
                if member.is_dir():
                    continue

                member_name = sanitize_filename(member.filename)
                suffix = Path(member_name).suffix.lower()
                if suffix not in set(self.settings.ALLOWED_IMAGE_EXTENSIONS):
                    continue

                target_path = output_dir / member_name
                with zf.open(member, "r") as src, target_path.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
                extracted.append(target_path)

        if not extracted:
            raise ValidationError("No valid image files found in ZIP archive")

        return extracted

    def cleanup_saved_file(self, path: str | Path) -> None:
        """Delete saved temporary file when not configured for persistence."""
        self.temp_manager.cleanup_file(path, preserve=bool(self.settings.SAVE_UPLOADS))
