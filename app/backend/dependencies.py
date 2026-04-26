"""Dependency providers for services, security hooks, and request context."""

from __future__ import annotations

from fastapi import Depends, Request

from app.backend.config import Settings, get_settings
from app.backend.constants import DEFAULT_REQUEST_ID
from app.backend.core.security import apply_rate_limit, authenticate_api_key
from app.backend.services.cache_service import CacheService
from app.backend.services.explainability_service import ExplainabilityService
from app.backend.services.file_service import FileService
from app.backend.services.inference_service import InferenceService
from app.backend.services.model_service import ModelService
from app.backend.services.postprocess_status_service import PostprocessStatusService
from app.backend.services.report_service import ReportService
from app.backend.services.video_service import VideoService


def get_request_id(request: Request) -> str:
    """Resolve request ID from request state with safe fallback."""
    return str(getattr(request.state, "request_id", DEFAULT_REQUEST_ID))


def get_settings_dep() -> Settings:
    """Dependency wrapper for application settings."""
    return get_settings()


def get_model_service() -> ModelService:
    """Dependency provider for model service singleton."""
    return ModelService.get_instance()


def get_file_service() -> FileService:
    """Dependency provider for file service singleton."""
    return FileService.get_instance()


def get_inference_service() -> InferenceService:
    """Dependency provider for inference service singleton."""
    return InferenceService.get_instance()


def get_explainability_service() -> ExplainabilityService:
    """Dependency provider for explainability service singleton."""
    return ExplainabilityService.get_instance()


def get_report_service() -> ReportService:
    """Dependency provider for report service singleton."""
    return ReportService.get_instance()


def get_postprocess_status_service() -> PostprocessStatusService:
    """Dependency provider for postprocess status service singleton."""
    return PostprocessStatusService.get_instance()


def get_cache_service(settings: Settings = Depends(get_settings_dep)) -> CacheService:
    """Dependency provider for cache service singleton."""
    return CacheService.get_instance(ttl_seconds=int(settings.PREDICTION_CACHE_TTL))


def get_video_service() -> VideoService:
    """Dependency provider for video service singleton."""
    return VideoService.get_instance()


def enforce_auth(request: Request, settings: Settings = Depends(get_settings_dep)) -> None:
    """Enforce optional API-key authentication."""
    authenticate_api_key(request=request, settings=settings)


def enforce_rate_limit(request: Request, settings: Settings = Depends(get_settings_dep)) -> None:
    """Enforce optional in-memory rate limiting."""
    apply_rate_limit(request=request, settings=settings)


def secure_endpoint(
    _auth: None = Depends(enforce_auth),
    _rate: None = Depends(enforce_rate_limit),
) -> None:
    """Composable dependency for auth + rate limit checks."""
    return None
