"""Stub route for webcam prediction integration guidance."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.backend.config import get_settings
from app.backend.core.exceptions import InferenceError
from app.backend.dependencies import get_request_id, secure_endpoint
from app.backend.schemas.common import BaseResponse
from app.backend.utils.logger import configure_logger

router = APIRouter(prefix="/predict/webcam", tags=["predict"], dependencies=[Depends(secure_endpoint)])
settings = get_settings()
logger = configure_logger("backend.routes.predict_webcam_stub", settings.LOG_LEVEL, f"{settings.OUTPUT_DIR}/logs")


@router.post("", response_model=BaseResponse)
def predict_webcam_stub(request_id: str = Depends(get_request_id)) -> BaseResponse:
    """Return a clear statement that server-side webcam access is unsupported."""
    try:
        return BaseResponse(
            success=False,
            request_id=request_id,
            message=(
                "Server-side webcam capture is not supported for security and privacy reasons. "
                "Use client-side webcam capture and upload frames/videos to predict endpoints."
            ),
            data={
                "supported": False,
                "reason": "Webcam devices are client-local resources and are not exposed by backend API",
            },
            errors=[],
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Webcam stub route failed request_id=%s", request_id)
        raise InferenceError("Webcam stub failed", details={"cause": str(exc)}) from exc
