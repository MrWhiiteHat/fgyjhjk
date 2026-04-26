"""Video prediction API route for uploaded video files."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.concurrency import run_in_threadpool

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
from app.backend.schemas.responses import VideoPredictionData, VideoPredictionResponse
from app.backend.services.file_service import FileService
from app.backend.services.inference_service import InferenceService
from app.backend.services.model_service import ModelService
from app.backend.services.report_service import ReportService
from app.backend.utils.logger import configure_logger

router = APIRouter(prefix="/predict/video", tags=["predict"], dependencies=[Depends(secure_endpoint)])
settings = get_settings()
logger = configure_logger("backend.routes.predict_video", settings.LOG_LEVEL, f"{settings.OUTPUT_DIR}/logs")


@router.post("", response_model=VideoPredictionResponse)
async def predict_video(
    request: Request,
    file: UploadFile = File(...),
    threshold: float | None = Form(default=None),
    frame_stride: int | None = Form(default=None, ge=1),
    max_frames: int | None = Form(default=None, ge=0),
    aggregation_strategy: str = Form(default="mean_probability"),
    generate_report: bool = Form(default=False),
    save_annotated_output: bool = Form(default=False),
    request_id: str = Depends(get_request_id),
    file_service: FileService = Depends(get_file_service),
    inference_service: InferenceService = Depends(get_inference_service),
    report_service: ReportService = Depends(get_report_service),
    model_service: ModelService = Depends(get_model_service),
) -> VideoPredictionResponse:
    """Run video prediction endpoint using uploaded video file."""
    logger.info("ROUTE_START | request_id=%s filename=%s size=%s", request_id, file.filename, file.size)
    saved_video = await file_service.save_video_upload(file)
    logger.info("ROUTE_FILE_SAVED | path=%s bytes=%d", saved_video.saved_path, saved_video.size_bytes)

    requested_frame_stride = int(frame_stride) if frame_stride is not None else int(settings.VIDEO_DEFAULT_FRAME_STRIDE)
    effective_frame_stride = max(1, min(requested_frame_stride, int(settings.VIDEO_MAX_FRAME_STRIDE)))

    requested_max_frames = int(max_frames) if (max_frames is not None and int(max_frames) > 0) else int(settings.VIDEO_DEFAULT_MAX_FRAMES)
    effective_max_frames = max(1, min(requested_max_frames, int(settings.VIDEO_MAX_FRAMES_PER_REQUEST)))

    try:
        try:
            logger.info("ROUTE_VIDEO_DISPATCH | request_id=%s stride=%d max_frames=%d", request_id, effective_frame_stride, effective_max_frames)
            video_payload = await run_in_threadpool(
                inference_service.predict_video_file,
                video_path=str(saved_video.saved_path.as_posix()),
                threshold=threshold,
                frame_stride=effective_frame_stride,
                max_frames=effective_max_frames,
                aggregation_strategy=aggregation_strategy,
                file_digest=saved_video.sha256,
                save_annotated_output=save_annotated_output,
            )
            logger.info("ROUTE_VIDEO_RETURNED | request_id=%s frames=%s", request_id, video_payload.get("num_frames_processed", 0))

            report_payload = None
            report_id = None
            if bool(generate_report) and bool(settings.ENABLE_REPORT_EXPORT) and bool(settings.SAVE_REPORTS):
                logger.info("ROUTE_REPORT_START | request_id=%s", request_id)
                report_payload = await run_in_threadpool(
                    report_service.create_report,
                    request_metadata={
                        "request_id": request_id,
                        "route": str(request.url.path),
                    },
                    file_metadata={
                        "original_filename": saved_video.original_filename,
                        "safe_filename": saved_video.safe_filename,
                        "size_bytes": saved_video.size_bytes,
                        "content_type": saved_video.content_type,
                        "sha256": saved_video.sha256,
                    },
                    prediction_results={
                        **video_payload.get("result", {}),
                        "summary": video_payload.get("summary", {}),
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
                logger.info("ROUTE_REPORT_DONE | request_id=%s report_id=%s", request_id, report_id)

            prediction = await run_in_threadpool(
                inference_service.build_prediction_response,
                raw_result=video_payload["result"],
                explanation_available=False,
                report_id=report_id,
            )

            data = VideoPredictionData(
                result=prediction,
                num_frames_processed=int(video_payload.get("num_frames_processed", 0)),
                fake_frame_ratio=float(video_payload.get("fake_frame_ratio", 0.0)),
                aggregation_strategy=str(video_payload.get("aggregation_strategy", "")),
                aggregated_probability=float(video_payload.get("aggregated_probability", 0.0)),
                aggregated_label=str(video_payload.get("aggregated_label", "")),
                frame_report_path=str(video_payload.get("frame_report_path", "")),
                cache_hit=bool(video_payload.get("cache_hit", False)),
                metadata_summary={
                    "filename": saved_video.original_filename,
                    "content_type": saved_video.content_type,
                    "size_bytes": saved_video.size_bytes,
                    "sha256": saved_video.sha256,
                    "effective_frame_stride": effective_frame_stride,
                    "effective_max_frames": effective_max_frames,
                    "save_annotated_output": bool(save_annotated_output),
                },
            )

            logger.info("ROUTE_RESPONSE_BUILD | request_id=%s label=%s", request_id, prediction.get("predicted_label"))
            return VideoPredictionResponse(
                success=True,
                request_id=request_id,
                message="Video prediction completed",
                data=data,
                errors=[],
            )
        except AppBaseError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("Video prediction failed request_id=%s", request_id)
            raise InferenceError("Video prediction failed", details={"cause": str(exc)}) from exc
    finally:
        file_service.cleanup_saved_file(saved_video.saved_path)
