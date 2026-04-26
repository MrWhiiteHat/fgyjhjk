"""Image prediction API route using inference and explainability services."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.backend.config import get_settings
from app.backend.core.exceptions import AppBaseError, InferenceError
from app.backend.dependencies import (
    get_explainability_service,
    get_file_service,
    get_inference_service,
    get_model_service,
    get_report_service,
    get_request_id,
    secure_endpoint,
)
from app.backend.schemas.responses import ImagePredictionData, ImagePredictionResponse
from app.backend.services.explainability_service import ExplainabilityService
from app.backend.services.file_service import FileService
from app.backend.services.inference_service import InferenceService
from app.backend.services.model_service import ModelService
from app.backend.services.report_service import ReportService
from app.backend.utils.logger import configure_logger

router = APIRouter(prefix="/predict/image", tags=["predict"], dependencies=[Depends(secure_endpoint)])
settings = get_settings()
logger = configure_logger("backend.routes.predict_image", settings.LOG_LEVEL, f"{settings.OUTPUT_DIR}/logs")


def _to_artifact_url(path_value: str) -> str:
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


def _compact_explainability_payload(payload: dict | None) -> dict | None:
    """Keep only lightweight explainability fields for report persistence."""
    if not payload:
        return None
    return {
        "explanation_type": str(payload.get("explanation_type", "")),
        "target_layer": str(payload.get("target_layer", "")),
        "heatmap_path": str(payload.get("heatmap_path", "")),
        "overlay_path": str(payload.get("overlay_path", "")),
        "generated_at": str(payload.get("generated_at", "")),
    }


@router.post("", response_model=ImagePredictionResponse)
async def predict_image(
    request: Request,
    file: UploadFile = File(...),
    threshold: float | None = Form(default=None),
    explain: bool = Form(default=False),
    generate_report: bool = Form(default=False),
    request_id: str = Depends(get_request_id),
    file_service: FileService = Depends(get_file_service),
    inference_service: InferenceService = Depends(get_inference_service),
    explain_service: ExplainabilityService = Depends(get_explainability_service),
    report_service: ReportService = Depends(get_report_service),
    model_service: ModelService = Depends(get_model_service),
) -> ImagePredictionResponse:
    """Run single-image prediction with optional explainability and report generation."""
    logger.info("ROUTE_START | request_id=%s filename=%s size=%s", request_id, file.filename, file.size)
    saved = await file_service.save_image_upload(file)
    logger.info("ROUTE_FILE_SAVED | path=%s bytes=%d sha256=%s", saved.saved_path, saved.size_bytes, saved.sha256[:16])

    try:
        try:
            # Use the timeout-protected inference path to prevent infinite hangs.
            logger.info("ROUTE_INFERENCE_DISPATCH | request_id=%s entering threadpool", request_id)
            inference_payload = await run_in_threadpool(
                inference_service.predict_image_with_timeout,
                image_path=str(saved.saved_path.as_posix()),
                threshold=threshold,
                file_digest=saved.sha256,
            )
            logger.info("ROUTE_INFERENCE_RETURNED | request_id=%s cache_hit=%s", request_id, inference_payload.get("cache_hit"))

            raw_result = inference_payload["result"]
            warnings: list[str] = []
            explanation_payload = None

            if bool(explain) and not bool(settings.ENABLE_EXPLAINABILITY):
                warnings.append("Explainability is disabled on this server")

            if bool(explain) and bool(settings.ENABLE_EXPLAINABILITY):
                try:
                    logger.info("ROUTE_EXPLAIN_START | request_id=%s", request_id)
                    # Pass the already-computed prediction result to avoid a
                    # redundant forward pass inside the explainability service.
                    full_explanation_payload = await run_in_threadpool(
                        explain_service.explain_image,
                        image_path=str(saved.saved_path.as_posix()),
                        prediction_result=raw_result,
                        explanation_type="gradcam",
                        target_layer=None,
                    )
                    explanation_payload = _compact_explainability_payload(full_explanation_payload)
                    if explanation_payload is not None:
                        explanation_payload["heatmap_path"] = _to_artifact_url(
                            str(explanation_payload.get("heatmap_path", ""))
                        )
                        explanation_payload["overlay_path"] = _to_artifact_url(
                            str(explanation_payload.get("overlay_path", ""))
                        )
                    logger.info("ROUTE_EXPLAIN_DONE | request_id=%s", request_id)
                except AppBaseError as exc:
                    logger.warning("Explainability skipped request_id=%s cause=%s", request_id, exc.message)
                    warnings.append(f"Explainability unavailable: {exc.message}")
                    explanation_payload = None
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Explainability skipped request_id=%s", request_id)
                    warnings.append("Explainability unavailable due to internal error")
                    explanation_payload = None

            report_payload = None
            report_id = None
            if bool(generate_report) and (not bool(settings.ENABLE_REPORT_EXPORT) or not bool(settings.SAVE_REPORTS)):
                warnings.append("Report generation is disabled on this server")

            if bool(generate_report) and bool(settings.ENABLE_REPORT_EXPORT) and bool(settings.SAVE_REPORTS):
                try:
                    logger.info("ROUTE_REPORT_START | request_id=%s", request_id)
                    report_payload = await run_in_threadpool(
                        report_service.create_report,
                        request_metadata={
                            "request_id": request_id,
                            "route": str(request.url.path),
                        },
                        file_metadata={
                            "original_filename": saved.original_filename,
                            "safe_filename": saved.safe_filename,
                            "size_bytes": saved.size_bytes,
                            "content_type": saved.content_type,
                            "sha256": saved.sha256,
                        },
                        prediction_results={
                            **raw_result,
                            "timing": inference_payload.get("timing", {}),
                        },
                        explanation_outputs=explanation_payload,
                        model_metadata=model_service.get_model_info(),
                    )
                    report_id = report_payload.get("report_id")
                    report_payload["files"] = {
                        "json": f"/api/v1/reports/{report_id}/download?format=json",
                        "txt": f"/api/v1/reports/{report_id}/download?format=txt",
                        "csv": f"/api/v1/reports/{report_id}/download?format=csv",
                    }
                    logger.info("ROUTE_REPORT_DONE | request_id=%s report_id=%s", request_id, report_id)
                except AppBaseError as exc:
                    logger.warning("Report generation skipped request_id=%s cause=%s", request_id, exc.message)
                    warnings.append(f"Report generation unavailable: {exc.message}")
                    report_payload = None
                    report_id = None
                except Exception:  # noqa: BLE001
                    logger.exception("Report generation skipped request_id=%s", request_id)
                    warnings.append("Report generation unavailable due to internal error")
                    report_payload = None
                    report_id = None

            prediction_result = await run_in_threadpool(
                inference_service.build_prediction_response,
                raw_result=raw_result,
                explanation_available=bool(explanation_payload),
                report_id=report_id,
            )

            data = ImagePredictionData(
                prediction=prediction_result,
                timing=inference_payload.get("timing", {}),
                cache_hit=bool(inference_payload.get("cache_hit", False)),
                metadata_summary={
                    "filename": saved.original_filename,
                    "content_type": saved.content_type,
                    "size_bytes": saved.size_bytes,
                    "sha256": saved.sha256,
                    "warnings": warnings,
                },
                explainability=explanation_payload,
                report=report_payload,
            )

            logger.info("ROUTE_RESPONSE_BUILD | request_id=%s label=%s", request_id, prediction_result.get("predicted_label"))
            return ImagePredictionResponse(
                success=True,
                request_id=request_id,
                message="Image prediction completed with warnings" if warnings else "Image prediction completed",
                data=data,
                errors=[],
            )
        except AppBaseError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("Image prediction failed request_id=%s", request_id)
            raise InferenceError("Image prediction failed", details={"cause": str(exc)}) from exc
    finally:
        file_service.cleanup_saved_file(saved.saved_path)
