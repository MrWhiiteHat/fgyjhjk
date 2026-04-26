"""Admin routes for model metadata, reload operations, and metrics snapshots."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse

from app.backend.config import get_settings
from app.backend.core.exceptions import AppBaseError, InferenceError
from app.backend.dependencies import (
    get_cache_service,
    get_model_service,
    get_request_id,
    secure_endpoint,
)
from app.backend.schemas.requests import AdminReloadRequest
from app.backend.schemas.responses import ModelInfoData, ModelInfoResponse
from app.backend.services.cache_service import CacheService
from app.backend.services.model_service import ModelService
from app.backend.core.telemetry import get_telemetry
from app.backend.utils.logger import configure_logger

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(secure_endpoint)])
settings = get_settings()
logger = configure_logger("backend.routes.admin", settings.LOG_LEVEL, f"{settings.OUTPUT_DIR}/logs")


@router.get("/model-info", response_model=ModelInfoResponse)
def model_info(
    request_id: str = Depends(get_request_id),
    model_service: ModelService = Depends(get_model_service),
) -> ModelInfoResponse:
    """Return model metadata including artifact and load status."""
    try:
        info = model_service.get_model_info()
        data = ModelInfoData(
            model_name=str(info.get("model_name", "")),
            artifact_path=str(info.get("artifact_path", "")),
            threshold=float(info.get("threshold", 0.5)),
            loaded_at=str(info.get("loaded_at", "")),
            device=str(info.get("device", "")),
            explainability_enabled=bool(info.get("explainability_enabled", False)),
            model_type=str(info.get("model_type", "")),
        )
        return ModelInfoResponse(
            success=True,
            request_id=request_id,
            message="Model info retrieved",
            data=data,
            errors=[],
        )
    except AppBaseError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Model info route failed request_id=%s", request_id)
        raise InferenceError("Failed to retrieve model info", details={"cause": str(exc)}) from exc


@router.post("/reload-model", response_model=ModelInfoResponse)
def reload_model(
    payload: AdminReloadRequest,
    request_id: str = Depends(get_request_id),
    model_service: ModelService = Depends(get_model_service),
    cache_service: CacheService = Depends(get_cache_service),
) -> ModelInfoResponse:
    """Reload model safely and invalidate cache after successful load."""
    try:
        info = model_service.reload_model(
            strict_checkpoint_loading=not bool(payload.force),
            threshold=payload.threshold,
        )
        cache_service.invalidate_all()

        data = ModelInfoData(
            model_name=str(info.get("model_name", "")),
            artifact_path=str(info.get("artifact_path", "")),
            threshold=float(info.get("threshold", 0.5)),
            loaded_at=str(info.get("loaded_at", "")),
            device=str(info.get("device", "")),
            explainability_enabled=bool(info.get("explainability_enabled", False)),
            model_type=str(info.get("model_type", "")),
        )
        return ModelInfoResponse(
            success=True,
            request_id=request_id,
            message="Model reload completed",
            data=data,
            errors=[],
        )
    except AppBaseError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Model reload route failed request_id=%s", request_id)
        raise InferenceError("Model reload failed", details={"cause": str(exc)}) from exc


@router.get("/metrics", response_class=PlainTextResponse)
def metrics_snapshot(request: Request) -> PlainTextResponse:
    """Return Prometheus-compatible metrics output when enabled."""
    try:
        if not bool(settings.METRICS_ENABLED) or not bool(settings.PROMETHEUS_ENABLED):
            return PlainTextResponse("metrics_disabled 1\n", status_code=200)

        sections = [get_telemetry().prometheus_text()]
        media_type = "text/plain; version=0.0.4"

        ops_prometheus = getattr(request.app.state, "ops_prometheus", None)
        if ops_prometheus is not None:
            payload, media_type = ops_prometheus.render_latest()
            sections.append(payload.decode("utf-8", errors="replace"))

        text = "\n".join(section.rstrip("\n") for section in sections if section).rstrip("\n") + "\n"
        return PlainTextResponse(text, status_code=200, media_type=media_type)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Metrics route failed")
        raise InferenceError("Failed to render metrics", details={"cause": str(exc)}) from exc
