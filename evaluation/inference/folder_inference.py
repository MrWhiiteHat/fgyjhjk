"""Recursive folder inference with batch processing and robust error handling."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

import cv2
import pandas as pd
import torch
from tqdm import tqdm

from evaluation.explainability.overlay_utils import draw_prediction_overlay
from evaluation.utils.helpers import chunked, safe_div
from evaluation.utils.io import (
    collect_all_files_recursive,
    is_supported_extension,
    safe_read_image,
    save_dataframe_csv,
    save_dict_json,
    sanitize_filename,
    timestamp_for_filename,
)


REQUIRED_COLUMNS = [
    "filepath",
    "filename",
    "predicted_logit",
    "predicted_probability",
    "predicted_label",
    "threshold_used",
    "inference_time_ms",
    "status",
    "error_message",
]

CONTRACT_COLUMNS = [
    "input_id",
    "input_path",
    "predicted_label",
    "predicted_probability",
    "predicted_logit",
    "threshold_used",
    "model_name",
    "checkpoint_path",
    "inference_time_ms",
    "status",
    "error_message",
]


def run_folder_inference(
    input_dir: str | Path,
    predictor: Any,
    preprocessor: Any,
    config: Dict,
    logger: logging.Logger,
) -> Dict:
    """Run recursive folder inference and export per-file records."""
    root = Path(input_dir)
    if not root.exists() or not root.is_dir():
        raise NotADirectoryError(f"Input folder does not exist or is not a directory: {root}")

    output_root = Path(config.get("output_dir", "evaluation/outputs"))
    prediction_dir = output_root / "predictions"
    prediction_dir.mkdir(parents=True, exist_ok=True)

    all_files = collect_all_files_recursive(root)
    image_extensions = config.get("image_extensions", [".jpg", ".jpeg", ".png", ".bmp", ".webp"])

    valid_image_paths: List[Path] = []
    rows: List[Dict] = []

    for path in all_files:
        if is_supported_extension(path, image_extensions):
            valid_image_paths.append(path)
        else:
            logger.info("Skipping unsupported file extension: %s", path)
            rows.append(
                {
                    "input_id": str(path.as_posix()),
                    "input_path": str(path.as_posix()),
                    "filepath": str(path.as_posix()),
                    "filename": path.name,
                    "predicted_logit": 0.0,
                    "predicted_probability": 0.0,
                    "predicted_label": "",
                    "threshold_used": float(config.get("default_threshold", 0.5)),
                    "model_name": predictor.model_name,
                    "checkpoint_path": predictor.checkpoint_path,
                    "inference_time_ms": 0.0,
                    "status": "skipped",
                    "error_message": "unsupported_extension",
                }
            )

    batch_size = int(config.get("batch_size", 16))
    threshold = float(config.get("default_threshold", 0.5))

    for batch_paths in tqdm(list(chunked(valid_image_paths, batch_size)), desc="Folder inference"):
        batch_tensors: List[torch.Tensor] = []
        batch_ids: List[str] = []
        prep_failed: List[Dict] = []

        for image_path in batch_paths:
            prep = preprocessor.preprocess_image_path(image_path)
            if prep.status != "ok" or prep.tensor is None:
                logger.warning("Unreadable or invalid image skipped: %s | %s", image_path, prep.error_message)
                prep_failed.append(
                    {
                        "input_id": str(image_path.as_posix()),
                        "input_path": str(image_path.as_posix()),
                        "filepath": str(image_path.as_posix()),
                        "filename": image_path.name,
                        "predicted_logit": 0.0,
                        "predicted_probability": 0.0,
                        "predicted_label": "",
                        "threshold_used": threshold,
                        "model_name": predictor.model_name,
                        "checkpoint_path": predictor.checkpoint_path,
                        "inference_time_ms": 0.0,
                        "status": "error",
                        "error_message": prep.error_message or "preprocess_failed",
                    }
                )
                continue

            batch_tensors.append(prep.tensor)
            batch_ids.append(str(image_path.as_posix()))

        rows.extend(prep_failed)

        if not batch_tensors:
            continue

        tensor_batch = torch.stack(batch_tensors, dim=0)
        batch_results = predictor.predict_batch(batch_tensor=tensor_batch, threshold=threshold, input_ids=batch_ids)

        for prediction in batch_results:
            path_str = str(prediction.get("input_id", ""))
            file_path = Path(path_str)
            row = {
                "input_id": path_str,
                "input_path": path_str,
                "filepath": path_str,
                "filename": file_path.name,
                "predicted_logit": float(prediction.get("predicted_logit", 0.0)),
                "predicted_probability": float(prediction.get("predicted_probability", 0.0)),
                "predicted_label": str(prediction.get("predicted_label", "")),
                "threshold_used": float(prediction.get("threshold_used", threshold)),
                "model_name": str(prediction.get("model_name", predictor.model_name)),
                "checkpoint_path": str(prediction.get("checkpoint_path", predictor.checkpoint_path)),
                "inference_time_ms": float(prediction.get("inference_time_ms", 0.0)),
                "status": str(prediction.get("status", "error")),
                "error_message": str(prediction.get("error_message", "")),
            }
            rows.append(row)

            if bool(config.get("save_annotated_images", True)) and row["status"] == "ok":
                _save_annotated_folder_image(
                    image_path=file_path,
                    prediction=row,
                    input_root=root,
                    output_root=prediction_dir / "annotated_folder",
                    logger=logger,
                )

    table = pd.DataFrame(rows)
    for column in REQUIRED_COLUMNS:
        if column not in table.columns:
            table[column] = "" if column in {"filename", "predicted_label", "status", "error_message", "filepath"} else 0.0

    contract_table = table.copy()
    for column in CONTRACT_COLUMNS:
        if column not in contract_table.columns:
            contract_table[column] = "" if column in {"input_id", "input_path", "predicted_label", "model_name", "checkpoint_path", "status", "error_message"} else 0.0

    ordered_columns = REQUIRED_COLUMNS + [
        col for col in ["input_id", "input_path", "model_name", "checkpoint_path"] if col in table.columns
    ]
    table = table[ordered_columns]

    csv_path = prediction_dir / "folder_inference_predictions.csv"
    save_dataframe_csv(table, csv_path)

    json_path = prediction_dir / "folder_inference_predictions.json"
    if bool(config.get("save_prediction_json", True)):
        save_dict_json({"records": table.to_dict(orient="records")}, json_path)

    success_table = table[table["status"] == "ok"].copy()

    total_real = int((success_table["predicted_label"].astype(str).str.upper() == "REAL").sum()) if not success_table.empty else 0
    total_fake = int((success_table["predicted_label"].astype(str).str.upper() == "FAKE").sum()) if not success_table.empty else 0

    if not success_table.empty:
        confidence = success_table.apply(
            lambda row: row["predicted_probability"] if str(row["predicted_label"]).upper() == "FAKE" else (1.0 - float(row["predicted_probability"])),
            axis=1,
        )
        avg_confidence = float(confidence.mean())
        fastest_ms = float(success_table["inference_time_ms"].min())
        slowest_ms = float(success_table["inference_time_ms"].max())
    else:
        avg_confidence = 0.0
        fastest_ms = 0.0
        slowest_ms = 0.0

    summary = {
        "input_dir": str(root.as_posix()),
        "total_files": int(len(all_files)),
        "total_valid_images": int(len(valid_image_paths)),
        "total_processed": int(len(success_table)),
        "total_real_predictions": total_real,
        "total_fake_predictions": total_fake,
        "average_confidence": avg_confidence,
        "fastest_inference_ms": fastest_ms,
        "slowest_inference_ms": slowest_ms,
        "error_count": int((table["status"] == "error").sum()),
        "skipped_count": int((table["status"] == "skipped").sum()),
        "predictions_csv": str(csv_path.as_posix()),
        "predictions_json": str(json_path.as_posix()) if bool(config.get("save_prediction_json", True)) else "",
    }

    summary_path = prediction_dir / "folder_inference_summary.json"
    save_dict_json(summary, summary_path)

    return {
        "summary": summary,
        "records": table,
        "result_contract_records": contract_table[CONTRACT_COLUMNS],
        "summary_path": str(summary_path.as_posix()),
    }


def _save_annotated_folder_image(
    image_path: Path,
    prediction: Dict,
    input_root: Path,
    output_root: Path,
    logger: logging.Logger,
) -> None:
    """Save annotated image preserving relative folder structure when possible."""
    image, error = safe_read_image(image_path)
    if image is None:
        logger.warning("Could not annotate %s: %s", image_path, error)
        return

    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    elif image.ndim == 3 and image.shape[2] == 4:
        image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)

    annotated = draw_prediction_overlay(
        image_bgr=image,
        predicted_label=str(prediction.get("predicted_label", "")),
        probability=float(prediction.get("predicted_probability", 0.0)),
        threshold=float(prediction.get("threshold_used", 0.5)),
        inference_time_ms=float(prediction.get("inference_time_ms", 0.0)),
    )

    try:
        relative = image_path.resolve().relative_to(input_root.resolve())
        output_path = output_root / relative
    except Exception:
        stamp = timestamp_for_filename()
        output_path = output_root / f"{sanitize_filename(image_path.stem)}_{stamp}{image_path.suffix}"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), annotated):
        logger.warning("Failed to save annotated image: %s", output_path)
