"""Archive guard for safe zip inspection without unsafe extraction."""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ArchiveGuardResult:
    """Inspection result for uploaded archive payload."""

    allowed: bool
    reason_codes: list[str] = field(default_factory=list)
    accepted_members: list[str] = field(default_factory=list)
    metadata: dict[str, float | int | str] = field(default_factory=dict)


class ArchiveGuard:
    """Inspects zip archives and rejects traversal or bomb-like patterns."""

    def inspect(
        self,
        *,
        archive_bytes: bytes,
        allowed_extensions: set[str],
        max_members: int = 500,
        max_depth: int = 5,
        max_uncompressed_bytes: int = 2 * 1024 * 1024 * 1024,
    ) -> ArchiveGuardResult:
        """Inspect archive entries securely and return safe member list."""

        reasons: list[str] = []
        accepted: list[str] = []
        total_uncompressed = 0

        try:
            with zipfile.ZipFile(io.BytesIO(archive_bytes), mode="r") as zf:
                infos = zf.infolist()
                if len(infos) > max_members:
                    reasons.append("archive_member_count_exceeded")

                for info in infos:
                    if info.is_dir():
                        continue

                    name = info.filename.replace("\\", "/")
                    parts = [part for part in name.split("/") if part]
                    if name.startswith("/") or ".." in parts:
                        reasons.append("archive_path_traversal")
                        continue
                    if len(parts) > max_depth:
                        reasons.append("archive_depth_exceeded")
                        continue

                    ext = Path(parts[-1]).suffix.lower()
                    if ext not in allowed_extensions:
                        continue

                    total_uncompressed += int(info.file_size)
                    if total_uncompressed > max_uncompressed_bytes:
                        reasons.append("archive_uncompressed_size_exceeded")
                        break

                    accepted.append(parts[-1])
        except zipfile.BadZipFile:
            reasons.append("invalid_archive")

        if not accepted and "invalid_archive" not in reasons:
            reasons.append("no_valid_members")

        allowed = not reasons
        return ArchiveGuardResult(
            allowed=allowed,
            reason_codes=sorted(set(reasons)) if reasons else ["ok"],
            accepted_members=accepted,
            metadata={
                "accepted_member_count": len(accepted),
                "uncompressed_bytes": total_uncompressed,
            },
        )
