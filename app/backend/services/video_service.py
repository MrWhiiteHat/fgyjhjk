"""Video inference orchestration service wrapping Module 4 video inference runtime."""

from __future__ import annotations

from typing import Any, Dict

from app.backend.config import get_settings
from app.backend.core.exceptions import InferenceError
from app.backend.services.model_service import ModelService


class VideoService:
    """Service to run video inference with configured frame controls."""

    _instance: "VideoService | None" = None

    def __init__(self) -> None:
        self.settings = get_settings()
        self.model_service = ModelService.get_instance()

    @classmethod
    def get_instance(cls) -> "VideoService":
        """Get singleton video service instance."""
        if cls._instance is None:
            cls._instance = VideoService()
        return cls._instance

    def predict_video(
        self,
        video_path: str,
        threshold: float | None,
        frame_stride: int,
        max_frames: int,
        aggregation_strategy: str,
        save_annotated_output: bool | None = None,
    ) -> Dict[str, Any]:
        """Run video inference and return structured summary."""
        predictor = self.model_service.get_predictor()
        preprocessor = self.model_service.get_preprocessor()

        config = self.model_service.get_eval_runtime_config()
        if threshold is not None:
            config["default_threshold"] = float(threshold)
            config["per_frame_threshold"] = float(threshold)
        config["frame_stride"] = int(frame_stride)
        config["max_frames_per_video"] = int(max_frames)
        config["aggregate_video_strategy"] = str(aggregation_strategy)
        config["batch_inference_size"] = max(1, int(self.settings.VIDEO_INFERENCE_BATCH_SIZE))
        config["save_video_output"] = bool(
            self.settings.SAVE_ANNOTATED_OUTPUTS if save_annotated_output is None else save_annotated_output
        )

        try:
            from evaluation.inference.video_inference import run_video_inference

            payload = run_video_inference(
                video_path=video_path,
                predictor=predictor,
                preprocessor=preprocessor,
                config=config,
                logger=self.model_service.logger,
            )
        except Exception as exc:
            raise InferenceError("Video inference execution failed", details={"cause": str(exc)}) from exc

        if payload.get("status") != "ok":
            raise InferenceError(payload.get("error_message", "Video inference failed"))

        summary = payload.get("summary", {})
        return {
            "num_frames_processed": int(summary.get("num_frames_processed", 0)),
            "fake_frame_ratio": float(summary.get("fake_frame_ratio", 0.0)),
            "aggregation_strategy": str(summary.get("aggregation_strategy", aggregation_strategy)),
            "aggregated_probability": float(summary.get("aggregated_probability", 0.0)),
            "aggregated_label": str(summary.get("aggregated_label", "")),
            "frame_report_path": str(summary.get("per_frame_csv", "")),
            "summary": summary,
            "result_contract": payload.get("result_contract", {}),
        }
