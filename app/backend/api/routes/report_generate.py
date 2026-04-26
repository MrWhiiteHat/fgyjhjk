"""Explicit report generation API route."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.backend.config import get_settings
from app.backend.core.exceptions import AppBaseError, InferenceError, ValidationError
from app.backend.dependencies import get_model_service, get_report_service, get_request_id, secure_endpoint
from app.backend.schemas.requests import GenerateReportRequest
from app.backend.schemas.responses import ReportData, ReportResponse
from app.backend.services.model_service import ModelService
from app.backend.services.report_service import ReportService
from app.backend.utils.logger import configure_logger

settings = get_settings()
logger = configure_logger("backend.routes.report_generate", settings.LOG_LEVEL, f"{settings.OUTPUT_DIR}/logs")

router = APIRouter(prefix="/report", tags=["reports"], dependencies=[Depends(secure_endpoint)])


@router.post("/generate", response_model=ReportResponse)
def generate_report(
    payload: GenerateReportRequest,
    request_id: str = Depends(get_request_id),
    report_service: ReportService = Depends(get_report_service),
    model_service: ModelService = Depends(get_model_service),
) -> ReportResponse:
    """Generate report artifacts explicitly from provided prediction payload."""
    try:
        if not payload.prediction_results:
            raise ValidationError("prediction_results must be provided for report generation")

        model_metadata = payload.model_metadata if payload.model_metadata is not None else model_service.get_model_info()

        result = report_service.create_report(
            request_metadata={"request_id": request_id, **payload.request_metadata},
            file_metadata=payload.file_metadata,
            prediction_results=payload.prediction_results,
            explanation_outputs=payload.explanation_outputs,
            model_metadata=model_metadata,
        )

        report_id = str(result["report_id"])
        files = {
            "json": f"/api/v1/reports/{report_id}/download?format=json",
            "txt": f"/api/v1/reports/{report_id}/download?format=txt",
            "csv": f"/api/v1/reports/{report_id}/download?format=csv",
        }

        data = ReportData(
            report_id=report_id,
            metadata=dict(result["metadata"]),
            files=files,
        )

        return ReportResponse(
            success=True,
            request_id=request_id,
            message="Report generated successfully",
            data=data,
            errors=[],
        )
    except AppBaseError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Report generation failed request_id=%s", request_id)
        raise InferenceError("Report generation failed", details={"cause": str(exc)}) from exc
