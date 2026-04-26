"""Retention policy sweeper for tenant storage artifacts."""

from __future__ import annotations

from pathlib import Path

from cloud.platform.utils.time import utc_now


class RetentionPolicyService:
    """Applies max-age retention policies to tenant directories."""

    def sweep(self, *, tenant_root: Path, max_age_seconds: int) -> int:
        """Delete files older than max_age_seconds and return deleted count."""

        safe_max_age = max(0, int(max_age_seconds))
        now_ts = int(utc_now().timestamp())
        deleted = 0

        if not tenant_root.exists():
            return 0

        for candidate in tenant_root.rglob("*"):
            if not candidate.is_file():
                continue
            age_seconds = now_ts - int(candidate.stat().st_mtime)
            if age_seconds > safe_max_age:
                candidate.unlink(missing_ok=True)
                deleted += 1

        return deleted
