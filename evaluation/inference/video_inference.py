"""Video inference runtime with frame-level predictions and video-level aggregation."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

import cv2
import numpy as np
import pandas as pd

from evaluation.explainability.overlay_utils import draw_prediction_overlay
from evaluation.utils.io import (
    is_supported_extension,
    safe_open_video,
    safe_video_writer,
    save_dataframe_csv,
    save_dict_json,
    save_key_value_lines,
    sanitize_filename,
    timestamp_for_filename,
)


PER_FRAME_COLUMNS = [
    "video_path",
    "frame_index",
    "timestamp_sec",
    "predicted_probability",
    "predicted_label",
    "threshold_used",
    "inference_time_ms",
]


def run_video_inference(
    video_path: str | Path,
    predictor: Any,
    preprocessor: Any,
    config: Dict,
    logger: logging.Logger,
) -> Dict:
    """Run configurable per-frame video inference and aggregate to video-level output."""
    input_video = Path(video_path)
    if not input_video.exists() or not input_video.is_file():
        return _error_payload(f"Video file does not exist: {input_video}")

    if not is_supported_extension(input_video, config.get("video_extensions", [".mp4", ".avi", ".mov", ".mkv", ".webm"])):
        return _error_payload(f"Unsupported video extension: {input_video.suffix}")

    capture, capture_error = safe_open_video(input_video)
    if capture is None:
        return _error_payload(capture_error or "Failed to open video stream")

    output_root = Path(config.get("output_dir", "evaluation/outputs"))
    prediction_dir = output_root / "predictions"
    prediction_dir.mkdir(parents=True, exist_ok=True)

    fps_value = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    fps_override = float(config.get("video_fps_override", 0) or 0)
    if fps_override > 0:
        fps = fps_override
    elif fps_value > 1e-6:
        fps = fps_value
    else:
        fps = 25.0
        logger.warning("Video FPS unavailable. Falling back to 25 FPS for timestamps.")

    frame_stride = max(1, int(config.get("frame_stride", 1)))
    max_frames = int(config.get("max_frames_per_video", 0))
    per_frame_threshold = float(config.get("per_frame_threshold", config.get("default_threshold", 0.5)))
    batch_inference_size = max(1, int(config.get("batch_inference_size", 1)))

    frame_rows: List[Dict] = []
    processed_probabilities: List[float] = []
    processed_labels: List[int] = []
    processed_inference_ms: List[float] = []

    writer = None
    writer_path = ""
    written_frames = 0

    save_video_output = bool(config.get("save_video_output", True))
    total_frames_read = 0
    processed_frames = 0
    dropped_frames = 0

    current_display_label = "N/A"
    current_display_prob = 0.0
    current_display_ms = 0.0

    pending_frames: List[np.ndarray] = []
    pending_indices: List[int] = []

    def _record_prediction(frame_index: int, prediction: Dict[str, Any]) -> None:
        nonlocal processed_frames
        nonlocal current_display_label
        nonlocal current_display_prob
        nonlocal current_display_ms

        if prediction.get("status") != "ok":
            logger.warning(
                "Per-frame prediction failed at frame=%d | error=%s",
                frame_index,
                prediction.get("error_message", "unknown"),
            )
            return

        probability = float(prediction.get("predicted_probability", 0.0))
        label_text = str(prediction.get("predicted_label", ""))
        threshold_used = float(prediction.get("threshold_used", per_frame_threshold))
        inference_ms = float(prediction.get("inference_time_ms", 0.0))
        label_index = int(prediction.get("predicted_label_index", int(probability >= threshold_used)))

        processed_probabilities.append(probability)
        processed_labels.append(label_index)
        processed_inference_ms.append(inference_ms)
        processed_frames += 1

        current_display_label = label_text
        current_display_prob = probability
        current_display_ms = inference_ms

        frame_rows.append(
            {
                "video_path": str(input_video.as_posix()),
                "frame_index": int(frame_index),
                "timestamp_sec": float(frame_index / max(fps, 1e-8)),
                "predicted_probability": probability,
                "predicted_label": label_text,
                "threshold_used": threshold_used,
                "inference_time_ms": inference_ms,
            }
        )

    def _predict_one(frame_index: int, frame: np.ndarray) -> None:
        prediction = predictor.predict_numpy_image(
            image=frame,
            preprocessor=preprocessor,
            threshold=per_frame_threshold,
            input_id=f"{input_video.as_posix()}::frame_{frame_index}",
            assume_bgr=True,
        )
        _record_prediction(frame_index=frame_index, prediction=prediction)

    def _flush_pending_batch() -> None:
        if not pending_frames:
            return

        if batch_inference_size <= 1:
            for frame_index, frame in zip(pending_indices, pending_frames):
                _predict_one(frame_index=frame_index, frame=frame)
            pending_frames.clear()
            pending_indices.clear()
            return

        input_ids = [f"{input_video.as_posix()}::frame_{frame_index}" for frame_index in pending_indices]

        try:
            batch_tensor, preprocess_results = preprocessor.preprocess_batch_numpy(
                images=pending_frames,
                assume_bgr=True,
                input_ids=input_ids,
            )
        except Exception as exc:
            logger.warning(
                "Batch preprocessing failed; falling back to per-frame prediction | cause=%s",
                exc,
            )
            batch_tensor = None
            preprocess_results = []

        if batch_tensor is None or not preprocess_results:
            for frame_index, frame in zip(pending_indices, pending_frames):
                _predict_one(frame_index=frame_index, frame=frame)
            pending_frames.clear()
            pending_indices.clear()
            return

        valid_ids: List[str] = []
        valid_frame_indices: List[int] = []

        for idx, preprocess_result in enumerate(preprocess_results):
            if preprocess_result.status == "ok" and preprocess_result.tensor is not None:
                valid_ids.append(str(preprocess_result.metadata.get("input_id", input_ids[idx])))
                valid_frame_indices.append(int(pending_indices[idx]))
            else:
                logger.warning(
                    "Per-frame preprocessing failed at frame=%d | error=%s",
                    int(pending_indices[idx]),
                    preprocess_result.error_message or "unknown",
                )

        batch_predictions: List[Dict[str, Any]] = []
        if valid_ids:
            try:
                batch_predictions = predictor.predict_batch(
                    batch_tensor=batch_tensor,
                    threshold=per_frame_threshold,
                    input_ids=valid_ids,
                )
            except Exception as exc:
                logger.warning(
                    "Batch prediction failed; falling back to per-frame prediction | cause=%s",
                    exc,
                )
                batch_predictions = []

        if valid_ids and len(batch_predictions) == len(valid_ids):
            for frame_index, prediction in zip(valid_frame_indices, batch_predictions):
                _record_prediction(frame_index=frame_index, prediction=prediction)
        else:
            for frame_index, frame in zip(pending_indices, pending_frames):
                _predict_one(frame_index=frame_index, frame=frame)

        pending_frames.clear()
        pending_indices.clear()

    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                if total_frames_read == 0:
                    return _error_payload("Video stream returned zero frames (broken video or codec issue)")
                break

            if frame is None or frame.size == 0:
                dropped_frames += 1
                total_frames_read += 1
                continue

            total_frames_read += 1
            frame_index = total_frames_read - 1

            if writer is None and save_video_output:
                writer_file = prediction_dir / f"{sanitize_filename(input_video.stem)}_{timestamp_for_filename()}_annotated.mp4"
                writer, writer_error = safe_video_writer(
                    output_path=writer_file,
                    fps=fps,
                    frame_width=int(frame.shape[1]),
                    frame_height=int(frame.shape[0]),
                )
                if writer is None:
                    logger.warning("Video output disabled due to writer failure: %s", writer_error)
                    save_video_output = False
                else:
                    writer_path = str(writer_file.as_posix())

            if max_frames > 0 and pending_frames and (processed_frames + len(pending_frames)) >= max_frames:
                _flush_pending_batch()

            should_process = (frame_index % frame_stride == 0)
            if max_frames > 0 and (processed_frames + len(pending_frames)) >= max_frames:
                should_process = False

            if should_process:
                pending_frames.append(frame)
                pending_indices.append(frame_index)
                if len(pending_frames) >= batch_inference_size:
                    _flush_pending_batch()

            if writer is not None and save_video_output:
                frame_to_write = draw_prediction_overlay(
                    image_bgr=frame,
                    predicted_label=current_display_label,
                    probability=current_display_prob,
                    threshold=per_frame_threshold,
                    inference_time_ms=current_display_ms,
                )
                writer.write(frame_to_write)
                written_frames += 1

            if max_frames > 0 and processed_frames >= max_frames:
                break

        if pending_frames:
            _flush_pending_batch()

    finally:
        capture.release()
        if writer is not None:
            writer.release()

    if save_video_output and writer is not None and written_frames == 0:
        logger.warning("Video writer produced no frames. Annotated video output is empty.")

    if processed_frames == 0:
        return _error_payload("No frames were processed for inference")

    frame_table = pd.DataFrame(frame_rows)
    for column in PER_FRAME_COLUMNS:
        if column not in frame_table.columns:
            frame_table[column] = 0.0 if column != "predicted_label" else ""
    frame_table = frame_table[PER_FRAME_COLUMNS]

    frame_csv_path = prediction_dir / f"{sanitize_filename(input_video.stem)}_per_frame_predictions.csv"
    save_dataframe_csv(frame_table, frame_csv_path)

    aggregation_strategy = str(config.get("aggregate_video_strategy", "mean_probability")).strip().lower()
    aggregation_window = max(1, int(config.get("aggregation_window", 1)))
    aggregate_min_fake_ratio = float(config.get("aggregate_video_min_fake_ratio", 0.35))

    agg_probability, agg_label, fake_frame_ratio = _aggregate_video_prediction(
        probabilities=processed_probabilities,
        labels=processed_labels,
        strategy=aggregation_strategy,
        threshold=float(config.get("default_threshold", 0.5)),
        min_fake_ratio=aggregate_min_fake_ratio,
        window=aggregation_window,
    )

    summary = {
        "video_path": str(input_video.as_posix()),
        "aggregated_probability": float(agg_probability),
        "aggregated_label": str(agg_label),
        "num_frames_processed": int(processed_frames),
        "num_frames_read": int(total_frames_read),
        "dropped_frames": int(dropped_frames),
        "fake_frame_ratio": float(fake_frame_ratio),
        "aggregation_strategy": aggregation_strategy,
        "aggregation_window": int(aggregation_window),
        "per_frame_csv": str(frame_csv_path.as_posix()),
        "annotated_video_path": writer_path,
        "fps_used": float(fps),
    }

    avg_inference_ms = float(np.mean(np.asarray(processed_inference_ms, dtype=np.float64))) if processed_inference_ms else 0.0
    eps = 1e-8
    clipped_prob = min(max(float(agg_probability), eps), 1.0 - eps)
    aggregated_logit = float(np.log(clipped_prob / (1.0 - clipped_prob)))

    result_contract = {
        "input_path": str(input_video.as_posix()),
        "input_id": str(input_video.as_posix()),
        "predicted_label": str(agg_label),
        "predicted_probability": float(agg_probability),
        "predicted_logit": aggregated_logit,
        "threshold_used": float(config.get("default_threshold", 0.5)),
        "model_name": str(getattr(predictor, "model_name", "")),
        "checkpoint_path": str(getattr(predictor, "checkpoint_path", "")),
        "inference_time_ms": avg_inference_ms,
        "status": "ok",
        "error_message": "",
    }

    summary_json_path = prediction_dir / f"{sanitize_filename(input_video.stem)}_video_summary.json"
    summary_txt_path = prediction_dir / f"{sanitize_filename(input_video.stem)}_video_summary.txt"

    save_dict_json(summary, summary_json_path)
    save_key_value_lines(summary_txt_path, summary)

    summary["summary_json"] = str(summary_json_path.as_posix())
    summary["summary_txt"] = str(summary_txt_path.as_posix())
    summary["result_contract"] = result_contract

    return {
        "status": "ok",
        "error_message": "",
        "summary": summary,
        "per_frame_table": frame_table,
        "result_contract": result_contract,
    }


def _aggregate_video_prediction(
    probabilities: List[float],
    labels: List[int],
    strategy: str,
    threshold: float,
    min_fake_ratio: float,
    window: int,
) -> Tuple[float, str, float]:
    """Aggregate frame-level predictions into one video-level prediction."""
    if not probabilities:
        return 0.0, "REAL", 0.0

    probs = np.asarray(probabilities, dtype=np.float64)
    labs = np.asarray(labels, dtype=np.int64)

    # Optional sliding-window smoothing if configured.
    if window > 1 and probs.size >= window:
        kernel = np.ones(window, dtype=np.float64) / float(window)
        probs_for_aggregation = np.convolve(probs, kernel, mode="valid")
    else:
        probs_for_aggregation = probs

    fake_frame_ratio = float(np.mean(probs >= float(threshold)))

    if strategy == "mean_probability":
        agg_prob = float(np.mean(probs_for_aggregation))
    elif strategy == "max_probability":
        agg_prob = float(np.max(probs_for_aggregation))
    elif strategy == "fake_frame_ratio":
        agg_prob = float(fake_frame_ratio)
    elif strategy == "majority_vote":
        agg_prob = float(np.mean(labs))
    elif strategy == "sliding_window_mean":
        agg_prob = float(np.mean(probs_for_aggregation))
    elif strategy == "sliding_window_max":
        agg_prob = float(np.max(probs_for_aggregation))
    else:
        raise ValueError(
            "Unsupported aggregate_video_strategy. Supported values: "
            "mean_probability, max_probability, fake_frame_ratio, majority_vote, "
            "sliding_window_mean, sliding_window_max"
        )

    if strategy == "fake_frame_ratio":
        label = "FAKE" if fake_frame_ratio >= float(min_fake_ratio) else "REAL"
    else:
        label = "FAKE" if agg_prob >= float(threshold) else "REAL"

    return float(agg_prob), label, float(fake_frame_ratio)


def _error_payload(message: str) -> Dict:
    """Create standardized error payload for video inference failures."""
    return {
        "status": "error",
        "error_message": str(message),
        "summary": {},
        "per_frame_table": pd.DataFrame(columns=PER_FRAME_COLUMNS),
    }
