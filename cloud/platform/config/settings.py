"""Runtime settings for cloud platform services."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CloudSettings:
    """Settings sourced from environment variables with sensible defaults."""

    storage_root: Path = Path("cloud_data/storage")
    artifacts_root: Path = Path("cloud_data/artifacts")
    signed_url_secret: str = "change-me-for-production"
    signed_url_ttl_seconds: int = 900
    idempotency_ttl_seconds: int = 24 * 60 * 60
    webhook_signing_secret: str = "change-me-webhook-secret"
    max_job_retries: int = 3
    job_poll_interval_seconds: float = 0.2

    @staticmethod
    def from_env() -> "CloudSettings":
        """Build settings from process environment variables."""

        return CloudSettings(
            storage_root=Path(os.getenv("CLOUD_STORAGE_ROOT", "cloud_data/storage")),
            artifacts_root=Path(os.getenv("CLOUD_ARTIFACTS_ROOT", "cloud_data/artifacts")),
            signed_url_secret=os.getenv("CLOUD_SIGNED_URL_SECRET", "change-me-for-production"),
            signed_url_ttl_seconds=int(os.getenv("CLOUD_SIGNED_URL_TTL_SECONDS", "900")),
            idempotency_ttl_seconds=int(os.getenv("CLOUD_IDEMPOTENCY_TTL_SECONDS", str(24 * 60 * 60))),
            webhook_signing_secret=os.getenv("CLOUD_WEBHOOK_SIGNING_SECRET", "change-me-webhook-secret"),
            max_job_retries=int(os.getenv("CLOUD_MAX_JOB_RETRIES", "3")),
            job_poll_interval_seconds=float(os.getenv("CLOUD_JOB_POLL_INTERVAL_SECONDS", "0.2")),
        )

    def ensure_directories(self) -> None:
        """Create required directories if missing."""

        self.storage_root.mkdir(parents=True, exist_ok=True)
        self.artifacts_root.mkdir(parents=True, exist_ok=True)
