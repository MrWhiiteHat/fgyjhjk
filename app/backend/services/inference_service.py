"""Inference service orchestrating image, folder, and video predictions."""

from __future__ import annotations

import concurrent.futures
import time
from pathlib import Path
from typing import Any, Dict, List, Sequence

from app.backend.config import get_settings
from app.backend.core.exceptions import InferenceError, ValidationError
from app.backend.services.cache_service import CacheService
from app.backend.services.model_service import ModelService
from app.backend.services.video_service import VideoService
from app.backend.utils.helpers import hash_file
from app.backend.utils.logger import configure_logger

# Dedicated threadpool for inference with timeout support.
_INFERENCE_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=2, thread_name_prefix="inference"
)


class InferenceService:
    """Service layer for deterministic inference execution and response shaping."""

    _instance: "InferenceService | None" = None

    def __init__(self) -> None:
        self.settings = get_settings()
        self.logger = configure_logger(
            "backend.inference_service", self.settings.LOG_LEVEL, f"{self.settings.OUTPUT_DIR}/logs"
        )
        self.model_service = ModelService.get_instance()
        self.cache_service = CacheService.get_instance(ttl_seconds=int(self.settings.PREDICTION_CACHE_TTL))
        self.video_service = VideoService.get_instance()

    @classmethod
    def get_instance(cls) -> "InferenceService":
        """Get singleton inference service instance."""
        if cls._instance is None:
            cls._instance = InferenceService()
        return cls._instance

    def _build_cache_key(self, file_path: str, threshold: float, file_digest: str | None = None) -> str:
        """Build deterministic image-cache key from digest and model state."""
        digest = str(file_digest or "").strip() or hash_file(file_path)
        model_version = self.model_service.model_version
        return f"image|{digest}|{model_version}|{threshold:.6f}"

    def _build_video_cache_key(
        self,
        video_path: str,
        threshold: float,
        frame_stride: int,
        max_frames: int,
        aggregation_strategy: str,
        save_annotated_output: bool,
        file_digest: str | None = None,
    ) -> str:
        """Build deterministic video-cache key from digest, params, and model state."""
        digest = str(file_digest or "").strip() or hash_file(video_path)
        model_version = self.model_service.model_version
        return (
            f"video|{digest}|{model_version}|{threshold:.6f}|{int(frame_stride)}|"
            f"{int(max_frames)}|{str(aggregation_strategy).strip().lower()}|{int(bool(save_annotated_output))}"
        )

    def build_prediction_response(
        self,
        raw_result: Dict[str, Any],
        explanation_available: bool,
        report_id: str | None = None,
    ) -> Dict[str, Any]:
        """Convert raw predictor output into stable API contract payload."""
        threshold_used = float(raw_result.get("threshold_used", self.settings.DEFAULT_THRESHOLD))
        predicted_probability = float(raw_result.get("predicted_probability", 0.0))
        predicted_label = str(raw_result.get("predicted_label", "")).upper()

        if predicted_label == "FAKE":
            fake_probability = predicted_probability
        elif predicted_label == "REAL":
            fake_probability = 1.0 - predicted_probability
        else:
            fake_probability = predicted_probability

        fake_probability = max(0.0, min(1.0, fake_probability))
        authenticity_score = max(0.0, min(1.0, 1.0 - fake_probability))
        confidence_score = max(fake_probability, authenticity_score)
        uncertainty_margin = abs(fake_probability - threshold_used)
        uncertain_prediction = uncertainty_margin < float(self.settings.UNCERTAIN_MARGIN)

        if fake_probability >= 0.75:
            risk_level = "high"
        elif fake_probability >= 0.45:
            risk_level = "medium"
        else:
            risk_level = "low"

        return {
            "predicted_label": str(raw_result.get("predicted_label", "")),
            "predicted_probability": predicted_probability,
            "predicted_logit": float(raw_result.get("predicted_logit", 0.0)),
            "threshold_used": threshold_used,
            "inference_time_ms": float(raw_result.get("inference_time_ms", 0.0)),
            "model_name": str(raw_result.get("model_name", "")),
            "artifact_path": str(raw_result.get("checkpoint_path", self.settings.MODEL_ARTIFACT_PATH)),
            "confidence_score": float(confidence_score),
            "authenticity_score": float(authenticity_score),
            "risk_score": float(fake_probability),
            "risk_level": risk_level,
            "uncertain_prediction": bool(uncertain_prediction),
            "uncertainty_margin": float(uncertainty_margin),
            "final_decision": "UNCERTAIN" if uncertain_prediction else str(raw_result.get("predicted_label", "")),
            "explanation_available": bool(explanation_available),
            "report_id": report_id,
        }

    def predict_image_file(
        self,
        image_path: str,
        threshold: float | None = None,
        file_digest: str | None = None,
    ) -> Dict[str, Any]:
        """Run deterministic image inference with optional cache usage."""
        selected_threshold = float(threshold if threshold is not None else self.settings.DEFAULT_THRESHOLD)

        cache_key = self._build_cache_key(image_path, selected_threshold, file_digest=file_digest)
        cached = self.cache_service.get(cache_key, model_version=self.model_service.model_version)
        if cached is not None:
            self.logger.info("PREDICT_CACHE_HIT | key=%s", cache_key[:60])
            payload = dict(cached)
            payload["cache_hit"] = True
            return payload

        self.logger.info("PREDICT_START | path=%s threshold=%.4f", image_path, selected_threshold)

        self.logger.info("PREDICT_GET_PREDICTOR_START")
        predictor = self.model_service.get_predictor()
        preprocessor = self.model_service.get_preprocessor()
        self.logger.info("PREDICT_GET_PREDICTOR_DONE")

        self.logger.info("PREDICT_PREPROCESS_START")
        start_pre = time.perf_counter()
        preprocessed = preprocessor.preprocess_image_path(image_path)
        preprocessing_time_ms = (time.perf_counter() - start_pre) * 1000.0
        self.logger.info("PREDICT_PREPROCESS_DONE | status=%s ms=%.2f", preprocessed.status, preprocessing_time_ms)

        if preprocessed.status != "ok" or preprocessed.tensor is None:
            raise InferenceError("Image preprocessing failed", details={"error": preprocessed.error_message})

        self.logger.info("PREDICT_INFERENCE_START")
        start_model = time.perf_counter()
        result = predictor.predict_tensor(
            tensor=preprocessed.tensor,
            threshold=selected_threshold,
            input_id=str(Path(image_path).as_posix()),
        )
        model_time_ms = (time.perf_counter() - start_model) * 1000.0
        self.logger.info(
            "PREDICT_INFERENCE_DONE | label=%s prob=%.4f ms=%.2f",
            result.get("predicted_label", ""),
            result.get("predicted_probability", 0.0),
            model_time_ms,
        )

        if result.get("status") != "ok":
            raise InferenceError("Image inference failed", details={"error": result.get("error_message", "")})

        payload = {
            "result": result,
            "timing": {
                "preprocessing_time_ms": float(preprocessing_time_ms),
                "model_time_ms": float(model_time_ms),
                "end_to_end_time_ms": float(preprocessing_time_ms + model_time_ms),
            },
            "cache_hit": False,
        }

        self.cache_service.set(cache_key, payload, model_version=self.model_service.model_version)
        return payload

    def predict_image_with_timeout(
        self,
        image_path: str,
        threshold: float | None = None,
        file_digest: str | None = None,
        timeout_sec: float | None = None,
    ) -> Dict[str, Any]:
        """Wrap predict_image_file with a hard timeout to prevent infinite hangs."""
        effective_timeout = float(timeout_sec or self.settings.REQUEST_TIMEOUT_SEC)
        future = _INFERENCE_EXECUTOR.submit(
            self.predict_image_file,
            image_path=image_path,
            threshold=threshold,
            file_digest=file_digest,
        )
        try:
            return future.result(timeout=effective_timeout)
        except concurrent.futures.TimeoutError:
            future.cancel()
            self.logger.error(
                "PREDICT_TIMEOUT | path=%s timeout_sec=%.1f", image_path, effective_timeout
            )
            raise InferenceError(
                "Inference timed out",
                details={"timeout_sec": effective_timeout, "image_path": image_path},
            )

    def predict_folder(self, image_paths: Sequence[str], threshold: float | None = None) -> Dict[str, Any]:
        """Run folder/batch prediction over a list of image paths."""
        paths = [str(path) for path in image_paths]
        if not paths:
            raise ValidationError("Folder prediction requires at least one image")
        if len(paths) > int(self.settings.MAX_BATCH_SIZE):
            raise ValidationError(
                "Too many files for one request",
                details={"max_batch_size": int(self.settings.MAX_BATCH_SIZE), "received": len(paths)},
            )

        results: List[Dict[str, Any]] = []
        latencies: List[float] = []

        for image_path in paths:
            prediction = self.predict_image_file(image_path=image_path, threshold=threshold)
            result = prediction["result"]
            latencies.append(float(result.get("inference_time_ms", 0.0)))
            results.append(result)

        total = len(results)
        fake_count = sum(1 for row in results if str(row.get("predicted_label", "")).upper() == "FAKE")
        real_count = total - fake_count

        summary = {
            "total_files": total,
            "total_fake_predictions": fake_count,
            "total_real_predictions": real_count,
            "avg_inference_time_ms": float(sum(latencies) / total) if total else 0.0,
            "threshold_used": float(threshold if threshold is not None else self.settings.DEFAULT_THRESHOLD),
        }

        return {
            "results": results,
            "summary": summary,
        }

    def predict_video_file(
        self,
        video_path: str,
        threshold: float | None,
        frame_stride: int,
        max_frames: int,
        aggregation_strategy: str,
        file_digest: str | None = None,
        save_annotated_output: bool | None = None,
    ) -> Dict[str, Any]:
        """Run video inference using dedicated video service wrapper."""
        selected_threshold = float(threshold if threshold is not None else self.settings.DEFAULT_THRESHOLD)
        save_annotated = bool(self.settings.SAVE_ANNOTATED_OUTPUTS if save_annotated_output is None else save_annotated_output)

        cache_key = self._build_video_cache_key(
            video_path=video_path,
            threshold=selected_threshold,
            frame_stride=frame_stride,
            max_frames=max_frames,
            aggregation_strategy=aggregation_strategy,
            save_annotated_output=save_annotated,
            file_digest=file_digest,
        )
        cached = self.cache_service.get(cache_key, model_version=self.model_service.model_version)
        if cached is not None:
            self.logger.info("VIDEO_CACHE_HIT | key=%s", cache_key[:60])
            payload = dict(cached)
            payload["cache_hit"] = True
            return payload

        self.logger.info("VIDEO_PREDICT_START | path=%s stride=%d max_frames=%d", video_path, frame_stride, max_frames)
        payload = self.video_service.predict_video(
            video_path=video_path,
            threshold=selected_threshold,
            frame_stride=frame_stride,
            max_frames=max_frames,
            aggregation_strategy=aggregation_strategy,
            save_annotated_output=save_annotated,
        )
        self.logger.info("VIDEO_PREDICT_DONE | frames=%s", payload.get("num_frames_processed", 0))

        result_contract = payload.get("result_contract", {})
        if not result_contract:
            raise InferenceError("Video inference returned missing result contract")

        response_payload = {
            "result": result_contract,
            "num_frames_processed": int(payload.get("num_frames_processed", 0)),
            "fake_frame_ratio": float(payload.get("fake_frame_ratio", 0.0)),
            "aggregation_strategy": str(payload.get("aggregation_strategy", aggregation_strategy)),
            "aggregated_probability": float(payload.get("aggregated_probability", 0.0)),
            "aggregated_label": str(payload.get("aggregated_label", "")),
            "frame_report_path": str(payload.get("frame_report_path", "")),
            "summary": payload.get("summary", {}),
            "cache_hit": False,
        }

        self.cache_service.set(cache_key, response_payload, model_version=self.model_service.model_version)
        return response_payload
