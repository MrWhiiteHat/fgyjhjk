"""Application startup logic for preparing runtime dependencies."""

from __future__ import annotations

import threading
import time

from fastapi import FastAPI

from app.backend.config import get_settings
from app.backend.core.runtime_compat import apply_windows_torch_platform_patch
from app.backend.core.telemetry import get_telemetry
from app.backend.services.model_service import ModelService
from app.backend.utils.io import ensure_dirs
from app.backend.utils.logger import configure_logger
from app.backend.utils.temp_files import cleanup_old_temp_files

try:
    from ops.monitoring.prometheus_metrics import PrometheusMetrics
except Exception:  # noqa: BLE001
    PrometheusMetrics = None  # type: ignore[assignment]


def _background_preload(app: FastAPI, model_service: ModelService, logger) -> None:
    """Run model preload in a background thread so Uvicorn can accept requests immediately."""
    preload_started = time.perf_counter()
    try:
        logger.info("PRELOAD_BG_START | Loading model in background thread")
        model_service.load_model(strict_checkpoint_loading=True)
        elapsed = time.perf_counter() - preload_started
        logger.info("PRELOAD_BG_DONE | Model preload completed in %.2f seconds", elapsed)
    except Exception:  # noqa: BLE001
        logger.exception("PRELOAD_BG_FAILED | Background model preload failed; lazy loading will be used")
    finally:
        app.state.model_ready.set()
        logger.info("PRELOAD_BG_GATE | model_ready event set")


def on_startup(app: FastAPI) -> None:
    """Initialize directories, telemetry, and optional model preload."""
    settings = get_settings()

    ensure_dirs(
        [
            settings.TEMP_DIR,
            settings.OUTPUT_DIR,
            f"{settings.OUTPUT_DIR}/reports",
            f"{settings.OUTPUT_DIR}/uploads",
            f"{settings.OUTPUT_DIR}/logs",
        ]
    )

    logger = configure_logger("backend.startup", settings.LOG_LEVEL, f"{settings.OUTPUT_DIR}/logs")
    telemetry = get_telemetry()

    app.state.started = True
    app.state.telemetry = telemetry
    app.state.model_ready = threading.Event()

    if PrometheusMetrics is not None:
        app.state.ops_prometheus = PrometheusMetrics(
            enabled=bool(settings.PROMETHEUS_ENABLED),
            environment=str(settings.APP_ENV),
        )
    else:
        app.state.ops_prometheus = None

    logger.info("Starting %s in %s mode", settings.APP_NAME, settings.APP_ENV)
    logger.info("Model artifact path: %s", settings.MODEL_ARTIFACT_PATH)
    apply_windows_torch_platform_patch(logger)

    if bool(settings.TEMP_CLEANUP_ENABLED):
        removed = cleanup_old_temp_files(settings.TEMP_DIR, max_age_seconds=int(settings.TEMP_MAX_AGE_SECONDS))
        logger.info("Startup temp cleanup removed %d stale files", removed)

    model_service = ModelService.get_instance()
    app.state.model_service = model_service

    if bool(settings.MODEL_PRELOAD_ON_STARTUP):
        preload_thread = threading.Thread(
            target=_background_preload,
            args=(app, model_service, logger),
            daemon=True,
            name="model-preload",
        )
        preload_thread.start()
        logger.info("Model preload dispatched to background thread (non-blocking)")
    else:
        app.state.model_ready.set()
        logger.info("Startup model preload disabled; using lazy model loading")


def startup_event(app: FastAPI) -> None:
    """Wrapper for FastAPI startup event registration."""
    on_startup(app)
