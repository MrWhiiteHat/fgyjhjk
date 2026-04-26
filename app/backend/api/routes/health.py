"""Health and readiness endpoint routes."""

from __future__ import annotations

import time
from pathlib import Path

from fastapi import APIRouter, Depends, Request, Response

from app.backend.config import get_settings
from app.backend.constants import APP_VERSION
from app.backend.core.exceptions import AppBaseError, InferenceError
from app.backend.dependencies import get_model_service, get_request_id
from app.backend.schemas.responses import HealthData, HealthResponse, ReadyData, ReadyResponse
from app.backend.services.model_service import ModelService
from app.backend.utils.logger import configure_logger

router = APIRouter(tags=["health"])

logger = configure_logger("backend.routes.health", get_settings().LOG_LEVEL, f"{get_settings().OUTPUT_DIR}/logs")


@router.get("/health", response_model=HealthResponse)
def health_check(
    request: Request,
    request_id: str = Depends(get_request_id),
    model_service: ModelService = Depends(get_model_service),
) -> HealthResponse:
    """Return health/readiness payload including model state and uptime."""
    try:
        settings = get_settings()
        model_info = model_service.get_model_info()
        telemetry = getattr(request.app.state, "telemetry", None)
        started = telemetry.started_at if telemetry else time.time()

        # Check if background preload is still running
        model_ready_event = getattr(request.app.state, "model_ready", None)
        preload_in_progress = model_ready_event is not None and not model_ready_event.is_set()

        data = HealthData(
            app_status="ok",
            model_loaded=bool(model_info.get("loaded", False)),
            artifact_path=str(model_info.get("artifact_path", "")),
            device=str(model_info.get("device", settings.DEVICE)),
            uptime_seconds=float(max(time.time() - started, 0.0)),
            version=APP_VERSION,
        )

        message = "Health check successful"
        if preload_in_progress:
            message = "Health check successful (model preloading in background)"

        return HealthResponse(
            success=True,
            request_id=request_id,
            message=message,
            data=data,
            errors=[],
        )
    except AppBaseError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Health endpoint failed request_id=%s", request_id)
        raise InferenceError("Health check failed", details={"cause": str(exc)}) from exc


@router.get("/ready", response_model=ReadyResponse)
def ready_check(
    request: Request,
    response: Response,
    request_id: str = Depends(get_request_id),
    model_service: ModelService = Depends(get_model_service),
) -> ReadyResponse:
    """Return readiness payload based on model load status and artifact presence."""
    try:
        model_info = model_service.get_model_info()
        artifact_path = str(model_info.get("artifact_path", ""))
        artifact_exists = bool(artifact_path and Path(artifact_path).exists())
        model_loaded = bool(model_info.get("loaded", False))

        # Also check the background preload readiness gate
        model_ready_event = getattr(request.app.state, "model_ready", None)
        preload_complete = model_ready_event is None or model_ready_event.is_set()

        ready = bool(artifact_exists and model_loaded and preload_complete)

        response.status_code = 200 if ready else 503

        app_status = "ready" if ready else "not_ready"
        if not preload_complete:
            app_status = "preloading"

        data = ReadyData(
            ready=ready,
            app_status=app_status,
            model_loaded=model_loaded,
            artifact_path=artifact_path,
            artifact_exists=artifact_exists,
            last_load_error=str(model_info.get("last_load_error", "")),
            version=APP_VERSION,
        )

        return ReadyResponse(
            success=ready,
            request_id=request_id,
            message="Readiness check successful" if ready else "Readiness check failed",
            data=data,
            errors=[],
        )
    except AppBaseError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Ready endpoint failed request_id=%s", request_id)
        raise InferenceError("Readiness check failed", details={"cause": str(exc)}) from exc
