"""Input guard for media validation and malformed payload blocking."""

from __future__ import annotations

import hashlib
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, UnidentifiedImageError

try:
    import cv2  # type: ignore
except Exception:  # noqa: BLE001
    cv2 = None


@dataclass
class InputGuardConfig:
    """Configuration knobs for media guard enforcement."""

    max_image_bytes: int = 12 * 1024 * 1024
    max_video_bytes: int = 300 * 1024 * 1024
    max_image_width: int = 8192
    max_image_height: int = 8192
    max_video_width: int = 8192
    max_video_height: int = 8192
    min_dim: int = 16
    min_aspect_ratio: float = 0.15
    max_aspect_ratio: float = 6.0
    extreme_aspect_ratio: float = 10.0
    repeated_corrupted_header_threshold: int = 3


@dataclass
class InputGuardDecision:
    """Structured allow/block decision with reason codes."""

    action: str
    reason_codes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)


class InputGuard:
    """Validates image/video payloads and blocks suspicious malformed content."""

    _IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    _VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}

    def __init__(self, config: InputGuardConfig | None = None) -> None:
        self.config = config or InputGuardConfig()
        self._corrupted_header_counts: dict[str, int] = {}

    def evaluate(
        self,
        *,
        filename: str,
        payload: bytes,
        claimed_mime: str | None = None,
        source_key: str | None = None,
    ) -> InputGuardDecision:
        """Evaluate payload and return allow, allow_with_warning, or block."""

        reason_codes: list[str] = []
        warnings: list[str] = []
        metadata: dict[str, str] = {}

        safe_name = Path(str(filename)).name
        ext = Path(safe_name).suffix.lower().strip()
        kind = self._classify_kind(ext)
        if kind == "unknown":
            reason_codes.append("unsupported_extension")
            return InputGuardDecision(action="block", reason_codes=reason_codes, warnings=warnings, metadata=metadata)

        if not payload:
            reason_codes.append("empty_payload")
            return InputGuardDecision(action="block", reason_codes=reason_codes, warnings=warnings, metadata=metadata)

        if claimed_mime:
            mismatch = self._mime_mismatch(kind=kind, mime=claimed_mime)
            if mismatch:
                reason_codes.append("payload_mismatch")

        max_size = self.config.max_image_bytes if kind == "image" else self.config.max_video_bytes
        if len(payload) > max_size:
            reason_codes.append("payload_too_large")

        if kind == "image":
            image_decision = self._validate_image(payload)
            reason_codes.extend(image_decision["blocks"])
            warnings.extend(image_decision["warnings"])
            metadata.update(image_decision["metadata"])
        else:
            video_decision = self._validate_video(payload)
            reason_codes.extend(video_decision["blocks"])
            warnings.extend(video_decision["warnings"])
            metadata.update(video_decision["metadata"])

        if "malformed_content" in reason_codes:
            self._record_corrupted_header(payload=payload, source_key=source_key)
            if self._is_repeated_corrupted_header(payload=payload, source_key=source_key):
                reason_codes.append("repeated_corrupted_header")

        reason_codes = sorted(set(reason_codes))
        warnings = sorted(set(warnings))

        if reason_codes:
            return InputGuardDecision(action="block", reason_codes=reason_codes, warnings=warnings, metadata=metadata)
        if warnings:
            return InputGuardDecision(
                action="allow_with_warning",
                reason_codes=["warning_only"],
                warnings=warnings,
                metadata=metadata,
            )
        return InputGuardDecision(action="allow", reason_codes=["ok"], warnings=warnings, metadata=metadata)

    def _classify_kind(self, ext: str) -> str:
        """Map extension to media kind."""

        if ext in self._IMAGE_EXTS:
            return "image"
        if ext in self._VIDEO_EXTS:
            return "video"
        return "unknown"

    def _mime_mismatch(self, *, kind: str, mime: str) -> bool:
        """Check claimed MIME against inferred media kind."""

        normalized = str(mime).lower().strip()
        if kind == "image":
            return not normalized.startswith("image/")
        if kind == "video":
            return not normalized.startswith("video/")
        return True

    def _validate_image(self, payload: bytes) -> dict:
        """Validate image dimensions, channels, and ratio anomalies."""

        blocks: list[str] = []
        warnings: list[str] = []
        metadata: dict[str, str] = {}

        try:
            with Image.open(tempfile.SpooledTemporaryFile()) as _:
                pass
        except Exception:
            # This no-op context ensures Pillow lazy loader imports are initialized.
            pass

        try:
            with Image.open(tempfile.SpooledTemporaryFile(max_size=len(payload) + 1024)) as _:
                pass
        except Exception:
            pass

        try:
            with Image.open(_bytes_to_tempfile(payload)) as image:
                image.load()
                width, height = image.size
                channels = len(image.getbands())
        except (UnidentifiedImageError, OSError, ValueError):
            return {"blocks": ["malformed_content"], "warnings": warnings, "metadata": metadata}

        metadata["width"] = str(width)
        metadata["height"] = str(height)
        metadata["channels"] = str(channels)

        if width < self.config.min_dim or height < self.config.min_dim:
            blocks.append("extreme_dimensions")
        if width > self.config.max_image_width or height > self.config.max_image_height:
            blocks.append("extreme_dimensions")

        if channels not in {1, 3, 4}:
            blocks.append("invalid_color_channels")

        ratio = max(width / max(height, 1), height / max(width, 1))
        metadata["aspect_ratio"] = f"{ratio:.4f}"
        if ratio > self.config.extreme_aspect_ratio:
            blocks.append("weird_aspect_ratio")
        elif ratio > self.config.max_aspect_ratio or ratio < self.config.min_aspect_ratio:
            warnings.append("weird_aspect_ratio")

        return {"blocks": blocks, "warnings": warnings, "metadata": metadata}

    def _validate_video(self, payload: bytes) -> dict:
        """Validate video structure and key dimensional properties."""

        blocks: list[str] = []
        warnings: list[str] = []
        metadata: dict[str, str] = {}

        if cv2 is None:
            warnings.append("video_validation_limited_no_opencv")
            return {"blocks": blocks, "warnings": warnings, "metadata": metadata}

        with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as temp:
            temp.write(payload)
            temp_path = Path(temp.name)

        try:
            capture = cv2.VideoCapture(str(temp_path))
            opened = capture.isOpened()
            if not opened:
                blocks.append("malformed_content")
                return {"blocks": blocks, "warnings": warnings, "metadata": metadata}

            width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            capture.release()

            metadata["width"] = str(width)
            metadata["height"] = str(height)
            metadata["frame_count"] = str(frame_count)

            if width <= 0 or height <= 0:
                blocks.append("malformed_content")
            if width < self.config.min_dim or height < self.config.min_dim:
                blocks.append("extreme_dimensions")
            if width > self.config.max_video_width or height > self.config.max_video_height:
                blocks.append("extreme_dimensions")

            ratio = max(width / max(height, 1), height / max(width, 1)) if width and height else 0.0
            metadata["aspect_ratio"] = f"{ratio:.4f}"
            if ratio > self.config.extreme_aspect_ratio:
                blocks.append("weird_aspect_ratio")
            elif ratio > self.config.max_aspect_ratio or ratio < self.config.min_aspect_ratio:
                warnings.append("weird_aspect_ratio")

        finally:
            temp_path.unlink(missing_ok=True)

        return {"blocks": blocks, "warnings": warnings, "metadata": metadata}

    def _record_corrupted_header(self, *, payload: bytes, source_key: str | None) -> None:
        """Track repeated malformed header signatures per source."""

        digest = self._header_digest(payload, source_key)
        self._corrupted_header_counts[digest] = self._corrupted_header_counts.get(digest, 0) + 1

    def _is_repeated_corrupted_header(self, *, payload: bytes, source_key: str | None) -> bool:
        """Return true when malformed header repeats over threshold."""

        digest = self._header_digest(payload, source_key)
        return self._corrupted_header_counts.get(digest, 0) >= self.config.repeated_corrupted_header_threshold

    @staticmethod
    def _header_digest(payload: bytes, source_key: str | None) -> str:
        """Compute short digest from first bytes and optional source identity."""

        head = payload[:32]
        source = str(source_key or "")
        return hashlib.sha256(head + source.encode("utf-8")).hexdigest()


def _bytes_to_tempfile(payload: bytes):
    """Create temporary file-like object for Pillow byte decoding."""

    temp = tempfile.SpooledTemporaryFile(max_size=max(1024 * 1024, len(payload) + 1024))
    temp.write(payload)
    temp.seek(0)
    return temp
