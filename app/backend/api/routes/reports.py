"""Report retrieval API routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse

from app.backend.config import get_settings
from app.backend.core.exceptions import AppBaseError, ReportNotFoundError
from app.backend.dependencies import get_report_service, get_request_id, secure_endpoint
from app.backend.schemas.requests import ReportQueryRequest
from app.backend.schemas.responses import ReportData, ReportResponse
from app.backend.services.report_service import ReportService
from app.backend.utils.logger import configure_logger

router = APIRouter(prefix="/reports", tags=["reports"], dependencies=[Depends(secure_endpoint)])
settings = get_settings()
logger = configure_logger("backend.routes.reports", settings.LOG_LEVEL, f"{settings.OUTPUT_DIR}/logs")


@router.get("/{report_id}", response_model=ReportResponse)
def get_report(
    report_id: str,
    report_format: str = Query(default="json", alias="format"),
    request_id: str = Depends(get_request_id),
    report_service: ReportService = Depends(get_report_service),
) -> ReportResponse:
    """Fetch report metadata and artifact paths by report ID."""
    try:
        _ = ReportQueryRequest(report_format=report_format)
        payload = report_service.get_report(report_id)

        files = {
            "json": f"/api/v1/reports/{report_id}/download?format=json",
            "txt": f"/api/v1/reports/{report_id}/download?format=txt",
            "csv": f"/api/v1/reports/{report_id}/download?format=csv",
        }

        data = ReportData(
            report_id=payload["report_id"],
            metadata=payload["metadata"],
            files=files,
        )

        return ReportResponse(
            success=True,
            request_id=request_id,
            message="Report lookup successful",
            data=data,
            errors=[],
        )
    except AppBaseError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Report lookup failed request_id=%s report_id=%s", request_id, report_id)
        raise ReportNotFoundError(f"Failed to fetch report: {report_id}", details={"cause": str(exc)}) from exc


@router.get("/{report_id}/download")
def download_report_file(
    report_id: str,
    report_format: str = Query(default="json", alias="format"),
    report_service: ReportService = Depends(get_report_service),
) -> FileResponse:
    """Download report artifact file by report ID and format."""
    try:
        query = ReportQueryRequest(report_format=report_format)
        payload = report_service.get_report(report_id)
        source_path = str(payload.get("files", {}).get(query.report_format, "")).strip()

        if not source_path:
            raise ReportNotFoundError(f"Report artifact not available: {report_id}.{query.report_format}")

        artifact = Path(source_path)
        if not artifact.exists() or not artifact.is_file():
            raise ReportNotFoundError(f"Report artifact file not found: {artifact}")

        media_type = {
            "json": "application/json",
            "txt": "text/plain",
            "csv": "text/csv",
        }[query.report_format]
        return FileResponse(
            path=artifact,
            media_type=media_type,
            filename=f"{report_id}.{query.report_format}",
        )
    except AppBaseError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Report download failed report_id=%s format=%s", report_id, report_format)
        raise ReportNotFoundError(f"Failed to download report artifact: {report_id}", details={"cause": str(exc)}) from exc
