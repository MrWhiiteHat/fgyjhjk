"""Explainability runner combining Grad-CAM and saliency generation workflows."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import cv2
import numpy as np
import torch

from evaluation.explainability.gradcam import GradCAM
from evaluation.explainability.overlay_utils import (
    colorize_heatmap,
    overlay_heatmap_on_image,
    save_rgb_image,
    stack_explainability_triplet,
)
from evaluation.explainability.saliency import SaliencyExplainer
from evaluation.utils.helpers import now_compact_timestamp
from evaluation.utils.io import safe_read_image, sanitize_filename


class ExplainabilityRunner:
    """Generate and save explainability outputs for inference samples."""

    def __init__(
        self,
        predictor: Any,
        preprocessor: Any,
        config: Dict,
        logger: logging.Logger,
    ) -> None:
        self.predictor = predictor
        self.preprocessor = preprocessor
        self.config = config
        self.logger = logger

        self.enable_gradcam = bool(config.get("enable_gradcam", True))
        self.enable_saliency = bool(config.get("enable_saliency", True))
        self.target_layer = str(config.get("explain_target_layer", "backbone.layer4"))
        self.save_panels = bool(config.get("save_explainability_panels", False))
        self.max_image_side = max(0, int(config.get("explain_max_image_side", 1280)))

        output_dir = Path(config.get("output_dir", "evaluation/outputs"))
        self.explain_dir = output_dir / "explainability"
        self.explain_dir.mkdir(parents=True, exist_ok=True)

        self._gradcam: Optional[GradCAM] = None
        self._saliency: Optional[SaliencyExplainer] = None

        self._initialize_explainers()

    def _initialize_explainers(self) -> None:
        """Initialize available explainers based on model compatibility."""
        if self.predictor.artifact_type == "onnx":
            if self.enable_gradcam or self.enable_saliency:
                self.logger.warning(
                    "Explainability disabled for ONNX runtime because gradient hooks are unavailable."
                )
            self.enable_gradcam = False
            self.enable_saliency = False
            return

        if not isinstance(self.predictor.model, torch.nn.Module):
            self.logger.warning("Predictor model is not torch.nn.Module; explainability disabled")
            self.enable_gradcam = False
            self.enable_saliency = False
            return

        if self.enable_gradcam:
            try:
                self._gradcam = GradCAM(self.predictor.model, self.target_layer, self.logger)
            except Exception as exc:
                self._gradcam = None
                self.enable_gradcam = False
                self.logger.warning("Grad-CAM unavailable: %s", exc)

        if self.enable_saliency:
            try:
                self._saliency = SaliencyExplainer(self.predictor.model)
            except Exception as exc:
                self._saliency = None
                self.enable_saliency = False
                self.logger.warning("Saliency unavailable: %s", exc)

    def explain_image_path(
        self,
        image_path: str | Path,
        predicted_label_index: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Run preprocessing and generate explainability outputs for a disk image."""
        image, error = safe_read_image(image_path)
        if image is None:
            return {
                "status": "error",
                "error_message": error or "Image read failed",
                "gradcam": {},
                "saliency": {},
            }

        rgb = cv2.cvtColor(image[:, :, :3], cv2.COLOR_BGR2RGB) if image.ndim == 3 else np.repeat(image[:, :, None], 3, axis=2)

        if self.max_image_side > 0:
            height, width = int(rgb.shape[0]), int(rgb.shape[1])
            longest_side = max(height, width)
            if longest_side > self.max_image_side:
                scale = float(self.max_image_side) / float(longest_side)
                resized_w = max(1, int(round(width * scale)))
                resized_h = max(1, int(round(height * scale)))
                rgb = cv2.resize(rgb, (resized_w, resized_h), interpolation=cv2.INTER_AREA)
                self.logger.info(
                    "Explainability source resized from %sx%s to %sx%s",
                    width,
                    height,
                    resized_w,
                    resized_h,
                )

        prep = self.preprocessor.preprocess_numpy_image(
            image=image,
            assume_bgr=True,
            input_id=str(Path(image_path).as_posix()),
        )
        if prep.status != "ok" or prep.tensor is None:
            return {
                "status": "error",
                "error_message": prep.error_message,
                "gradcam": {},
                "saliency": {},
            }

        return self.explain_tensor(
            input_tensor=prep.tensor,
            original_rgb=rgb,
            input_id=str(Path(image_path).as_posix()),
            predicted_label_index=predicted_label_index,
        )

    def explain_tensor(
        self,
        input_tensor: torch.Tensor,
        original_rgb: np.ndarray,
        input_id: str,
        predicted_label_index: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Generate explainability outputs for one preprocessed tensor and source image."""
        if input_tensor.ndim != 3:
            return {
                "status": "error",
                "error_message": f"Expected tensor shape [C,H,W], got {tuple(input_tensor.shape)}",
                "gradcam": {},
                "saliency": {},
            }

        if original_rgb.ndim != 3 or original_rgb.shape[2] != 3:
            return {
                "status": "error",
                "error_message": f"Expected RGB image shape [H,W,3], got {original_rgb.shape}",
                "gradcam": {},
                "saliency": {},
            }

        if not self.enable_gradcam and not self.enable_saliency:
            return {
                "status": "skipped",
                "error_message": "No explainability methods enabled or supported",
                "gradcam": {},
                "saliency": {},
            }

        safe_name = sanitize_filename(Path(input_id).stem if Path(input_id).suffix else str(input_id))
        stamp = now_compact_timestamp()
        target_class = int(predicted_label_index if predicted_label_index is not None else 1)

        batch_tensor = input_tensor.unsqueeze(0).to(self.predictor.device)

        result: Dict[str, Any] = {
            "status": "ok",
            "error_message": "",
            "gradcam": {},
            "saliency": {},
        }

        if self.enable_gradcam and self._gradcam is not None:
            try:
                heatmap = self._gradcam.generate(batch_tensor, target_class=target_class)
                overlay = overlay_heatmap_on_image(original_rgb, heatmap)
                heat_rgb = colorize_heatmap(heatmap)

                gradcam_heat_path = self.explain_dir / f"{safe_name}_{stamp}_gradcam_heatmap.png"
                gradcam_overlay_path = self.explain_dir / f"{safe_name}_{stamp}_gradcam_overlay.png"

                save_rgb_image(gradcam_heat_path, heat_rgb)
                save_rgb_image(gradcam_overlay_path, overlay)

                gradcam_panel_path = ""
                if self.save_panels:
                    panel = stack_explainability_triplet(original_rgb, heatmap, overlay)
                    panel_path = self.explain_dir / f"{safe_name}_{stamp}_gradcam_panel.png"
                    save_rgb_image(panel_path, panel)
                    gradcam_panel_path = str(panel_path.as_posix())

                result["gradcam"] = {
                    "status": "ok",
                    "heatmap_path": str(gradcam_heat_path.as_posix()),
                    "overlay_path": str(gradcam_overlay_path.as_posix()),
                    "panel_path": gradcam_panel_path,
                }
            except Exception as exc:
                result["gradcam"] = {
                    "status": "error",
                    "error_message": str(exc),
                }

        if self.enable_saliency and self._saliency is not None:
            try:
                heatmap = self._saliency.generate(batch_tensor, target_class=target_class)
                overlay = overlay_heatmap_on_image(original_rgb, heatmap)
                heat_rgb = colorize_heatmap(heatmap)

                saliency_heat_path = self.explain_dir / f"{safe_name}_{stamp}_saliency_heatmap.png"
                saliency_overlay_path = self.explain_dir / f"{safe_name}_{stamp}_saliency_overlay.png"

                save_rgb_image(saliency_heat_path, heat_rgb)
                save_rgb_image(saliency_overlay_path, overlay)

                saliency_panel_path = ""
                if self.save_panels:
                    panel = stack_explainability_triplet(original_rgb, heatmap, overlay)
                    panel_path = self.explain_dir / f"{safe_name}_{stamp}_saliency_panel.png"
                    save_rgb_image(panel_path, panel)
                    saliency_panel_path = str(panel_path.as_posix())

                result["saliency"] = {
                    "status": "ok",
                    "heatmap_path": str(saliency_heat_path.as_posix()),
                    "overlay_path": str(saliency_overlay_path.as_posix()),
                    "panel_path": saliency_panel_path,
                }
            except Exception as exc:
                result["saliency"] = {
                    "status": "error",
                    "error_message": str(exc),
                }

        return result
