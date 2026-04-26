"""Folder prediction API route handling ZIP archive uploads."""

from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile

from app.backend.config import get_settings
from app.backend.core.exceptions import AppBaseError, InferenceError
from app.backend.dependencies import (
    get_file_service,
    get_inference_service,
    get_model_service,
    get_report_service,
    get_request_id,
    secure_endpoint,
)
from app.backend.schemas.responses import FolderPredictionData, FolderPredictionResponse
from app.backend.services.file_service import FileService
from app.backend.services.inference_service import InferenceService
from app.backend.services.model_service import ModelService
from app.backend.services.report_service import ReportService
from app.backend.utils.logger import configure_logger

router = APIRouter(prefix="/predict/folder", tags=["predict"], dependencies=[Depends(secure_endpoint)])
settings = get_settings()
logger = configure_logger("backend.routes.predict_folder", settings.LOG_LEVEL, f"{settings.OUTPUT_DIR}/logs")


@router.post("", response_model=FolderPredictionResponse)
async def predict_folder(
    request: Request,
    archive: UploadFile = File(...),
    threshold: float | None = Form(default=None),
    generate_report: bool = Form(default=True),
    request_id: str = Depends(get_request_id),
    file_service: FileService = Depends(get_file_service),
    inference_service: InferenceService = Depends(get_inference_service),
    report_service: ReportService = Depends(get_report_service),
    model_service: ModelService = Depends(get_model_service),
) -> FolderPredictionResponse:
    """Run folder prediction on images extracted from ZIP archive upload."""
    saved_archive = await file_service.save_archive_upload(archive)

    extracted_paths = []
    extraction_root = None

    try:
        try:
            extracted_paths = file_service.extract_zip_archive(saved_archive.saved_path)
            if extracted_paths:
                extraction_root = Path(extracted_paths[0]).parent

            folder_payload = inference_service.predict_folder(
                image_paths=[str(path.as_posix()) for path in extracted_paths],
                threshold=threshold,
            )

            results = [
                inference_service.build_prediction_response(raw_result=row, explanation_available=False)
                for row in folder_payload["results"]
            ]

            report_payload = None
            report_id = None
            if bool(generate_report) and bool(settings.ENABLE_REPORT_EXPORT) and bool(settings.SAVE_REPORTS):
                report_payload = report_service.create_report(
                    request_metadata={
                        "request_id": request_id,
                        "route": str(request.url.path),
                    },
                    file_metadata={
                        "original_filename": saved_archive.original_filename,
                        "safe_filename": saved_archive.safe_filename,
                        "size_bytes": saved_archive.size_bytes,
                        "content_type": saved_archive.content_type,
                        "sha256": saved_archive.sha256,
                        "num_extracted_files": len(extracted_paths),
                    },
                    prediction_results={
                        "rows": folder_payload["results"],
                        "summary": folder_payload["summary"],
                    },
                    explanation_outputs=None,
                    model_metadata=model_service.get_model_info(),
                )
                report_id = report_payload.get("report_id")
                report_payload["files"] = {
                    "json": f"/api/v1/reports/{report_id}/download?format=json",
                    "txt": f"/api/v1/reports/{report_id}/download?format=txt",
                    "csv": f"/api/v1/reports/{report_id}/download?format=csv",
                }

            data = FolderPredictionData(
                results=results,
                summary=folder_payload["summary"],
                report_id=report_id,
            )

            return FolderPredictionResponse(
                success=True,
                request_id=request_id,
                message="Folder prediction completed",
                data=data,
                errors=[],
            )
        except AppBaseError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("Folder prediction failed request_id=%s", request_id)
            raise InferenceError("Folder prediction failed", details={"cause": str(exc)}) from exc
    finally:
        file_service.cleanup_saved_file(saved_archive.saved_path)
        if extraction_root and extraction_root.exists():
            shutil.rmtree(extraction_root, ignore_errors=True)
