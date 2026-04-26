"""Application shutdown logic and graceful resource cleanup."""

from __future__ import annotations

from fastapi import FastAPI

from app.backend.config import get_settings
from app.backend.utils.logger import configure_logger
from app.backend.utils.temp_files import cleanup_old_temp_files


def on_shutdown(app: FastAPI) -> None:
    """Cleanup temporary files on shutdown."""
    settings = get_settings()
    logger = configure_logger("backend.shutdown", settings.LOG_LEVEL, f"{settings.OUTPUT_DIR}/logs")

    if bool(settings.TEMP_CLEANUP_ENABLED):
        removed = cleanup_old_temp_files(settings.TEMP_DIR, max_age_seconds=int(settings.TEMP_MAX_AGE_SECONDS))
        logger.info("Shutdown cleanup completed. Removed temporary files: %d", removed)
    else:
        logger.info("Shutdown cleanup skipped because TEMP_CLEANUP_ENABLED=false")

    app.state.started = False


def shutdown_event(app: FastAPI) -> None:
    """Wrapper for FastAPI shutdown event registration."""
    on_shutdown(app)
