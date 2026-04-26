"""Webcam inference runtime with resilient loop control and graceful shutdown."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List

import cv2
import pandas as pd

from evaluation.explainability.overlay_utils import draw_prediction_overlay
from evaluation.utils.io import save_dataframe_csv, save_dict_json, sanitize_filename, timestamp_for_filename


def run_webcam_inference(
    predictor: Any,
    preprocessor: Any,
    config: Dict,
    logger: logging.Logger,
) -> Dict:
    """Run webcam inference loop until quit key, interruption, or failure."""
    webcam_index = int(config.get("webcam_index", 0))
    cap = cv2.VideoCapture(webcam_index)
    if not cap.isOpened():
        return {
            "status": "error",
            "error_message": f"Webcam unavailable at index {webcam_index}",
            "summary": {},
        }

    output_root = Path(config.get("output_dir", "evaluation/outputs"))
    prediction_dir = output_root / "predictions"
    prediction_dir.mkdir(parents=True, exist_ok=True)

    snapshots_dir = prediction_dir / "webcam_snapshots"
    if bool(config.get("save_webcam_snapshots", False)):
        snapshots_dir.mkdir(parents=True, exist_ok=True)

    display_available = True
    if os.name != "nt" and not os.environ.get("DISPLAY"):
        display_available = False
        logger.warning("No display environment detected. Running webcam in headless mode.")

    window_name = "Real vs Fake Webcam Inference (Press q to quit, s to snapshot)"
    threshold = float(config.get("default_threshold", 0.5))

    prediction_rows: List[Dict] = []

    frame_count = 0
    read_failures = 0
    max_read_failures = 10
    running_fps = 0.0
    last_time = time.perf_counter()

    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None or frame.size == 0:
                read_failures += 1
                logger.warning("Webcam frame read failed (%d/%d)", read_failures, max_read_failures)
                if read_failures >= max_read_failures:
                    raise RuntimeError("Webcam frame read failed repeatedly")
                continue

            read_failures = 0
            frame_count += 1

            prediction = predictor.predict_numpy_image(
                image=frame,
                preprocessor=preprocessor,
                threshold=threshold,
                input_id=f"webcam_frame_{frame_count}",
                assume_bgr=True,
            )

            predicted_label = str(prediction.get("predicted_label", "N/A"))
            predicted_probability = float(prediction.get("predicted_probability", 0.0))
            inference_time_ms = float(prediction.get("inference_time_ms", 0.0))

            now = time.perf_counter()
            delta = max(now - last_time, 1e-8)
            instantaneous_fps = 1.0 / delta
            running_fps = instantaneous_fps if running_fps == 0 else (0.9 * running_fps + 0.1 * instantaneous_fps)
            last_time = now

            annotated = draw_prediction_overlay(
                image_bgr=frame,
                predicted_label=predicted_label,
                probability=predicted_probability,
                threshold=float(prediction.get("threshold_used", threshold)),
                inference_time_ms=inference_time_ms,
            )

            cv2.putText(
                annotated,
                f"FPS: {running_fps:.2f}",
                (10, 145),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 0),
                2,
                cv2.LINE_AA,
            )

            prediction_rows.append(
                {
                    "frame_index": frame_count,
                    "predicted_label": predicted_label,
                    "predicted_probability": predicted_probability,
                    "predicted_logit": float(prediction.get("predicted_logit", 0.0)),
                    "threshold_used": float(prediction.get("threshold_used", threshold)),
                    "inference_time_ms": inference_time_ms,
                    "runtime_fps": float(running_fps),
                    "status": str(prediction.get("status", "error")),
                    "error_message": str(prediction.get("error_message", "")),
                }
            )

            key = -1
            if display_available:
                try:
                    cv2.imshow(window_name, annotated)
                    key = cv2.waitKey(1) & 0xFF
                except cv2.error as exc:
                    logger.warning("OpenCV display unavailable (%s). Switching to headless webcam mode.", exc)
                    display_available = False
            else:
                headless_max = int(config.get("webcam_headless_max_frames", 0))
                if headless_max > 0 and frame_count >= headless_max:
                    logger.info("Reached webcam_headless_max_frames=%d. Stopping.", headless_max)
                    break

            if key in (ord("q"), 27):
                logger.info("Webcam inference stopped by user input.")
                break

            if key == ord("s") and bool(config.get("save_webcam_snapshots", False)):
                snapshot_path = snapshots_dir / f"snapshot_{timestamp_for_filename()}_{frame_count:06d}.jpg"
                if cv2.imwrite(str(snapshot_path), annotated):
                    logger.info("Saved webcam snapshot: %s", snapshot_path)
                else:
                    logger.warning("Failed to save webcam snapshot: %s", snapshot_path)

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Stopping webcam inference gracefully.")
    except Exception as exc:
        logger.error("Webcam inference failure: %s", exc)
        return {
            "status": "error",
            "error_message": str(exc),
            "summary": {
                "frames_processed": int(frame_count),
            },
        }
    finally:
        cap.release()
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass

    prediction_table = pd.DataFrame(prediction_rows)
    csv_path = prediction_dir / "webcam_predictions.csv"
    if bool(config.get("save_prediction_csv", True)) and not prediction_table.empty:
        save_dataframe_csv(prediction_table, csv_path)

    summary = {
        "webcam_index": webcam_index,
        "frames_processed": int(frame_count),
        "display_available": bool(display_available),
        "predictions_logged": int(len(prediction_rows)),
        "prediction_csv": str(csv_path.as_posix()) if csv_path.exists() else "",
        "avg_runtime_fps": float(prediction_table["runtime_fps"].mean()) if not prediction_table.empty else 0.0,
        "avg_inference_ms": float(prediction_table["inference_time_ms"].mean()) if not prediction_table.empty else 0.0,
    }

    if not prediction_table.empty:
        last_row = prediction_table.iloc[-1]
        result_contract = {
            "input_path": "",
            "input_id": f"webcam_frame_{int(last_row['frame_index'])}",
            "predicted_label": str(last_row["predicted_label"]),
            "predicted_probability": float(last_row["predicted_probability"]),
            "predicted_logit": float(last_row["predicted_logit"]),
            "threshold_used": float(last_row["threshold_used"]),
            "model_name": str(getattr(predictor, "model_name", "")),
            "checkpoint_path": str(getattr(predictor, "checkpoint_path", "")),
            "inference_time_ms": float(last_row["inference_time_ms"]),
            "status": str(last_row["status"]),
            "error_message": str(last_row["error_message"]),
        }
    else:
        result_contract = {
            "input_path": "",
            "input_id": "",
            "predicted_label": "",
            "predicted_probability": 0.0,
            "predicted_logit": 0.0,
            "threshold_used": float(config.get("default_threshold", 0.5)),
            "model_name": str(getattr(predictor, "model_name", "")),
            "checkpoint_path": str(getattr(predictor, "checkpoint_path", "")),
            "inference_time_ms": 0.0,
            "status": "error",
            "error_message": "No frames processed",
        }

    summary["result_contract"] = result_contract

    summary_json = prediction_dir / "webcam_summary.json"
    save_dict_json(summary, summary_json)

    return {
        "status": "ok",
        "error_message": "",
        "summary": summary,
        "result_contract": result_contract,
    }
