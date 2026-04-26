"""Single-image inference runtime with optional explainability outputs."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import cv2
import pandas as pd

from evaluation.explainability.overlay_utils import draw_prediction_overlay
from evaluation.utils.io import (
    is_supported_extension,
    safe_read_image,
    save_dataframe_csv,
    save_dict_json,
    sanitize_filename,
    timestamp_for_filename,
)


def run_image_inference(
    image_path: str | Path,
    predictor: Any,
    preprocessor: Any,
    config: Dict,
    logger: logging.Logger,
    explain_runner: Optional[Any] = None,
) -> Dict:
    """Run single-image inference and persist optional outputs."""
    image_file = Path(image_path)
    output_root = Path(config.get("output_dir", "evaluation/outputs"))
    prediction_dir = output_root / "predictions"
    explain_dir = output_root / "explainability"

    prediction_dir.mkdir(parents=True, exist_ok=True)
    explain_dir.mkdir(parents=True, exist_ok=True)

    if not image_file.exists() or not image_file.is_file():
        return {
            "status": "error",
            "error_message": f"Image file does not exist: {image_file}",
            "result": None,
            "explainability": {},
        }

    if not is_supported_extension(image_file, config.get("image_extensions", [".jpg", ".jpeg", ".png", ".bmp", ".webp"])):
        return {
            "status": "error",
            "error_message": f"Unsupported image extension: {image_file.suffix}",
            "result": None,
            "explainability": {},
        }

    result = predictor.predict_image_path(
        image_path=image_file,
        preprocessor=preprocessor,
        threshold=float(config.get("default_threshold", 0.5)),
    )

    explainability = {}
    if result.get("status") == "ok" and explain_runner is not None:
        try:
            explainability = explain_runner.explain_image_path(
                image_path=image_file,
                predicted_label_index=int(result.get("predicted_label_index", 1)),
            )
        except Exception as exc:
            explainability = {
                "status": "error",
                "error_message": str(exc),
            }

    if result.get("status") == "ok" and bool(config.get("save_annotated_images", True)):
        source_img, read_error = safe_read_image(image_file)
        if source_img is None:
            logger.warning("Could not annotate image due to read failure: %s", read_error)
        else:
            if source_img.ndim == 2:
                source_img = cv2.cvtColor(source_img, cv2.COLOR_GRAY2BGR)
            elif source_img.ndim == 3 and source_img.shape[2] == 4:
                source_img = cv2.cvtColor(source_img, cv2.COLOR_BGRA2BGR)

            annotated = draw_prediction_overlay(
                image_bgr=source_img,
                predicted_label=str(result.get("predicted_label", "")),
                probability=float(result.get("predicted_probability", 0.0)),
                threshold=float(result.get("threshold_used", config.get("default_threshold", 0.5))),
                inference_time_ms=float(result.get("inference_time_ms", 0.0)),
            )

            stem = sanitize_filename(image_file.stem)
            stamp = timestamp_for_filename()
            output_path = prediction_dir / f"{stem}_{stamp}_annotated.jpg"
            if not cv2.imwrite(str(output_path), annotated):
                logger.warning("Failed to save annotated image at %s", output_path)
            else:
                result["annotated_image_path"] = str(output_path.as_posix())

    if bool(config.get("save_prediction_csv", True)):
        csv_path = prediction_dir / "image_inference_predictions.csv"
        save_dataframe_csv(pd.DataFrame([result]), csv_path)

    if bool(config.get("save_prediction_json", True)):
        json_path = prediction_dir / "image_inference_predictions.json"
        save_dict_json({"result": result, "explainability": explainability}, json_path)

    return {
        "status": "ok" if result.get("status") == "ok" else "error",
        "error_message": result.get("error_message", ""),
        "result": result,
        "explainability": explainability,
    }
