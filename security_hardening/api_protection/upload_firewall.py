"""Upload firewall enforcing extension, MIME, and volume constraints."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from security_hardening.api_protection.content_limits import ContentLimits, is_within_bytes_limit


@dataclass
class UploadFirewallDecision:
    """Decision output for upload firewall checks."""

    allowed: bool
    action: str
    reason_codes: list[str] = field(default_factory=list)
    metadata: dict[str, float | int | str] = field(default_factory=dict)


class UploadFirewall:
    """Applies file-count, size, extension, and MIME consistency checks."""

    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
    ARCHIVE_EXTENSIONS = {".zip"}

    def __init__(self, limits: ContentLimits | None = None) -> None:
        self.limits = limits or ContentLimits()

    def evaluate(self, files: list[dict]) -> UploadFirewallDecision:
        """Evaluate request file list and return allow/block decision."""

        reasons: list[str] = []

        if len(files) > self.limits.max_files_per_request:
            reasons.append("file_count_limit_exceeded")

        total_bytes = 0
        for file_item in files:
            filename = str(file_item.get("filename", ""))
            ext = Path(filename).suffix.lower()
            mime = str(file_item.get("mime_type", "")).lower()
            size = int(file_item.get("size_bytes", 0))
            total_bytes += size

            if ext in self.IMAGE_EXTENSIONS:
                if not is_within_bytes_limit(size, self.limits.max_image_size_mb):
                    reasons.append("image_size_limit_exceeded")
                if not mime.startswith("image/"):
                    reasons.append("image_mime_extension_mismatch")
            elif ext in self.VIDEO_EXTENSIONS:
                if not is_within_bytes_limit(size, self.limits.max_video_size_mb):
                    reasons.append("video_size_limit_exceeded")
                if not mime.startswith("video/"):
                    reasons.append("video_mime_extension_mismatch")
            elif ext in self.ARCHIVE_EXTENSIONS:
                if not is_within_bytes_limit(size, self.limits.max_archive_size_mb):
                    reasons.append("archive_size_limit_exceeded")
                if not (mime == "application/zip" or mime == "application/octet-stream"):
                    reasons.append("archive_mime_extension_mismatch")
            else:
                reasons.append("unsupported_extension")

        if not is_within_bytes_limit(total_bytes, self.limits.max_total_payload_mb):
            reasons.append("total_payload_limit_exceeded")

        allowed = not reasons
        action = "allow" if allowed else "block"
        return UploadFirewallDecision(
            allowed=allowed,
            action=action,
            reason_codes=sorted(set(reasons)) if reasons else ["ok"],
            metadata={
                "file_count": len(files),
                "total_bytes": total_bytes,
            },
        )
