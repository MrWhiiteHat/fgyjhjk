"""Explainability API route for uploaded image inputs."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.backend.config import get_settings
from app.backend.core.exceptions import AppBaseError, ExplainabilityError
from app.backend.dependencies import (
    get_explainability_service,
    get_file_service,
    get_request_id,
    secure_endpoint,
)
from app.backend.schemas.responses import ExplainabilityData, ExplainabilityResponse
from app.backend.services.explainability_service import ExplainabilityService
from app.backend.services.file_service import FileService
from app.backend.utils.logger import configure_logger

router = APIRouter(prefix="/explain/image", tags=["explain"], dependencies=[Depends(secure_endpoint)])
settings = get_settings()
logger = configure_logger("backend.routes.explain", settings.LOG_LEVEL, f"{settings.OUTPUT_DIR}/logs")


def _to_artifact_url(path_value: str) -> str:
    """Convert artifact file path under OUTPUT_DIR into static URL."""
    raw = str(path_value or "").strip()
    if not raw:
        return ""

    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = (Path.cwd() / candidate).resolve()
    else:
        candidate = candidate.resolve()

    output_root = Path(settings.OUTPUT_DIR).resolve()
    try:
        relative = candidate.relative_to(output_root)
        return f"/artifacts/{relative.as_posix()}"
    except Exception:
        return raw


@router.post("", response_model=ExplainabilityResponse)
async def explain_image(
    file: UploadFile = File(...),
    explanation_type: str = Form(default="both"),
    target_layer: str | None = Form(default=None),
    request_id: str = Depends(get_request_id),
    file_service: FileService = Depends(get_file_service),
    explainability_service: ExplainabilityService = Depends(get_explainability_service),
) -> ExplainabilityResponse:
    """Generate Grad-CAM/saliency explainability for uploaded image."""
    saved = await file_service.save_image_upload(file)
    try:
        try:
            payload = explainability_service.explain_image(
                image_path=str(saved.saved_path.as_posix()),
                explanation_type=explanation_type,
                target_layer=target_layer,
            )

            data = ExplainabilityData(
                explanation_type=str(payload.get("explanation_type", explanation_type)),
                target_layer=str(payload.get("target_layer", target_layer or "")),
                heatmap_path=_to_artifact_url(str(payload.get("heatmap_path", ""))),
                overlay_path=_to_artifact_url(str(payload.get("overlay_path", ""))),
                generated_at=str(payload.get("generated_at", "")),
            )

            return ExplainabilityResponse(
                success=True,
                request_id=request_id,
                message="Explainability generation completed",
                data=data,
                errors=[],
            )
        except AppBaseError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("Explainability route failed request_id=%s", request_id)
            raise ExplainabilityError("Explainability request failed", details={"cause": str(exc)}) from exc
    finally:
        file_service.cleanup_saved_file(saved.saved_path)
