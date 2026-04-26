"""CLI entrypoint for webcam inference."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from evaluation.inference.predictor import Predictor
from evaluation.inference.preprocessing_adapter import InferencePreprocessor
from evaluation.inference.webcam_inference import run_webcam_inference
from evaluation.utils.helpers import load_yaml
from evaluation.utils.io import ensure_output_structure
from evaluation.utils.logger import get_logger, log_exception


def parse_args() -> argparse.Namespace:
    """Parse command-line args for webcam inference."""
    parser = argparse.ArgumentParser(description="Run real-time webcam inference")
    parser.add_argument("--config", type=str, default="evaluation/configs/eval_config.yaml", help="Evaluation config path")
    parser.add_argument("--webcam-index", type=int, default=-1, help="Optional webcam index override")
    parser.add_argument("--checkpoint", type=str, default="", help="Optional checkpoint override")
    parser.add_argument("--exported-model", type=str, default="", help="Optional exported model override")
    return parser.parse_args()


def main() -> None:
    """Execute webcam inference loop."""
    args = parse_args()
    config = load_yaml(args.config)

    if args.webcam_index >= 0:
        config["webcam_index"] = int(args.webcam_index)
    if args.checkpoint:
        config["checkpoint_path"] = args.checkpoint
    if args.exported_model:
        config["exported_model_path"] = args.exported_model

    output_dirs = ensure_output_structure(config.get("output_dir", "evaluation/outputs"))
    logger, _ = get_logger(
        name="infer_webcam",
        log_dir=output_dirs["reports"],
        log_level=str(config.get("log_level", "INFO")),
        log_filename="infer_webcam.log",
    )

    try:
        preprocessor = InferencePreprocessor(config=config)
        predictor = Predictor(config=config, logger=logger)

        payload = run_webcam_inference(
            predictor=predictor,
            preprocessor=preprocessor,
            config=config,
            logger=logger,
        )

        if payload.get("status") != "ok":
            print("Webcam Inference Ended")
            print("----------------------")
            print(f"Status: Failed")
            print(f"Reason: {payload.get('error_message', 'Webcam inference failed')}")
            return

        summary = payload.get("summary", {})
        print("Webcam Inference Complete")
        print("-------------------------")
        print(f"Webcam Index: {summary.get('webcam_index', config.get('webcam_index', 0))}")
        print(f"Frames Processed: {summary.get('frames_processed', 0)}")
        print(f"Average FPS: {float(summary.get('avg_runtime_fps', 0.0)):.2f}")
        print(f"Average Inference: {float(summary.get('avg_inference_ms', 0.0)):.2f} ms")
        print(f"Prediction CSV: {summary.get('prediction_csv', '')}")

    except Exception as exc:
        log_exception(logger, "Webcam inference failed", exc)
        raise


if __name__ == "__main__":
    main()
