"""Explainability service wrapping Module 4 Grad-CAM and saliency utilities."""

from __future__ import annotations

import time
from typing import Any, Dict

from app.backend.config import get_settings
from app.backend.core.exceptions import ExplainabilityError
from app.backend.services.model_service import ModelService
from app.backend.utils.helpers import now_utc_iso
from app.backend.utils.logger import configure_logger


class ExplainabilityService:
    """Service for generating explainability outputs from uploaded images."""

    _instance: "ExplainabilityService | None" = None

    def __init__(self) -> None:
        self.settings = get_settings()
        self.model_service = ModelService.get_instance()
        self.logger = configure_logger("backend.explainability_service", self.settings.LOG_LEVEL, f"{self.settings.OUTPUT_DIR}/logs")

    @classmethod
    def get_instance(cls) -> "ExplainabilityService":
        """Get singleton explainability service instance."""
        if cls._instance is None:
            cls._instance = ExplainabilityService()
        return cls._instance

    def explain_image(
        self,
        image_path: str,
        prediction_result: Dict[str, Any] | None = None,
        explanation_type: str = "both",
        target_layer: str | None = None,
        request_id: str | None = None,
    ) -> Dict[str, Any]:
        """Generate explainability artifacts for one image file.

        Args:
            image_path: Path to the image file.
            prediction_result: Optional pre-computed prediction result from
                the inference pipeline. When provided, the label index is
                extracted directly instead of running a redundant forward pass.
            explanation_type: One of 'gradcam', 'saliency', or 'both'.
            target_layer: Optional target layer override for Grad-CAM.
            request_id: Optional request ID for log correlation.
        """
        if not bool(self.settings.ENABLE_EXPLAINABILITY):
            raise ExplainabilityError("Explainability is disabled by configuration")

        started = time.perf_counter()
        self.logger.info("request_id=%s stage=explainability_started", request_id or "unknown-request")

        predictor = self.model_service.get_predictor()
        preprocessor = self.model_service.get_preprocessor()
        if str(getattr(predictor, "artifact_type", "")).lower() == "onnx":
            raise ExplainabilityError("Explainability is not supported for ONNX runtime artifacts")

        config = self.model_service.get_eval_runtime_config()
        exp_type = str(explanation_type).strip().lower()
        config["enable_gradcam"] = exp_type in {"gradcam", "both"}
        config["enable_saliency"] = exp_type in {"saliency", "both"}
        if target_layer:
            config["explain_target_layer"] = str(target_layer)

        try:
            from evaluation.explainability.explain_runner import ExplainabilityRunner

            runner = ExplainabilityRunner(
                predictor=predictor,
                preprocessor=preprocessor,
                config=config,
                logger=self.model_service.logger,
            )

            # Reuse existing prediction result to avoid a redundant forward pass.
            if prediction_result and prediction_result.get("status") == "ok":
                label_index = int(prediction_result.get("predicted_label_index", 1))
                self.logger.info("request_id=%s stage=reused_prediction label_index=%d", request_id or "unknown-request", label_index)
            else:
                self.logger.info("request_id=%s stage=running_prediction_for_explain", request_id or "unknown-request")
                prediction = predictor.predict_image_path(image_path=image_path, preprocessor=preprocessor)
                label_index = int(prediction.get("predicted_label_index", 1)) if prediction.get("status") == "ok" else 1

            payload = runner.explain_image_path(image_path=image_path, predicted_label_index=label_index)
        except Exception as exc:
            raise ExplainabilityError("Explainability generation failed", details={"cause": str(exc)}) from exc

        if payload.get("status") not in {"ok", "skipped"}:
            raise ExplainabilityError(payload.get("error_message", "Explainability generation failed"))

        gradcam = payload.get("gradcam", {})
        saliency = payload.get("saliency", {})

        chosen = gradcam if exp_type in {"gradcam", "both"} and gradcam.get("status") == "ok" else saliency
        if exp_type == "saliency" and saliency.get("status") == "ok":
            chosen = saliency

        heatmap_path = str(chosen.get("heatmap_path", ""))
        overlay_path = str(chosen.get("overlay_path", ""))

        result = {
            "explanation_type": exp_type,
            "target_layer": str(config.get("explain_target_layer", "")),
            "heatmap_path": heatmap_path,
            "overlay_path": overlay_path,
            "generated_at": now_utc_iso(),
            "raw": payload,
        }
        self.logger.info(
            "request_id=%s stage=explainability_finished duration_ms=%.2f",
            request_id or "unknown-request",
            (time.perf_counter() - started) * 1000.0,
        )
        return result
