"""CLI entrypoint for video inference with aggregation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from evaluation.inference.predictor import Predictor
from evaluation.inference.preprocessing_adapter import InferencePreprocessor
from evaluation.inference.video_inference import run_video_inference
from evaluation.utils.helpers import load_yaml
from evaluation.utils.io import ensure_output_structure
from evaluation.utils.logger import get_logger, log_exception


def parse_args() -> argparse.Namespace:
    """Parse command-line args for video inference."""
    parser = argparse.ArgumentParser(description="Run per-frame video inference and aggregate output")
    parser.add_argument("--config", type=str, default="evaluation/configs/eval_config.yaml", help="Evaluation config path")
    parser.add_argument("--video", type=str, required=True, help="Input video path")
    parser.add_argument("--frame-stride", type=int, default=0, help="Optional frame stride override")
    parser.add_argument("--max-frames", type=int, default=0, help="Optional max processed frames override")
    parser.add_argument("--checkpoint", type=str, default="", help="Optional checkpoint override")
    parser.add_argument("--exported-model", type=str, default="", help="Optional exported model override")
    return parser.parse_args()


def main() -> None:
    """Execute video inference pipeline."""
    args = parse_args()
    config = load_yaml(args.config)

    if args.frame_stride > 0:
        config["frame_stride"] = int(args.frame_stride)
    if args.max_frames > 0:
        config["max_frames_per_video"] = int(args.max_frames)
    if args.checkpoint:
        config["checkpoint_path"] = args.checkpoint
    if args.exported_model:
        config["exported_model_path"] = args.exported_model

    output_dirs = ensure_output_structure(config.get("output_dir", "evaluation/outputs"))
    logger, _ = get_logger(
        name="infer_video",
        log_dir=output_dirs["reports"],
        log_level=str(config.get("log_level", "INFO")),
        log_filename="infer_video.log",
    )

    try:
        preprocessor = InferencePreprocessor(config=config)
        predictor = Predictor(config=config, logger=logger)

        payload = run_video_inference(
            video_path=args.video,
            predictor=predictor,
            preprocessor=preprocessor,
            config=config,
            logger=logger,
        )

        if payload.get("status") != "ok":
            raise RuntimeError(payload.get("error_message", "Video inference failed"))

        summary = payload["summary"]
        print("Video Inference Complete")
        print("------------------------")
        print(f"Video: {summary.get('video_path', '')}")
        print(f"Aggregated Label: {summary.get('aggregated_label', '')}")
        print(f"Aggregated Probability: {float(summary.get('aggregated_probability', 0.0)):.4f}")
        print(f"Frames Processed: {summary.get('num_frames_processed', 0)}")
        print(f"Fake Frame Ratio: {float(summary.get('fake_frame_ratio', 0.0)):.4f}")
        print(f"Aggregation Strategy: {summary.get('aggregation_strategy', '')}")
        print(f"Per-frame CSV: {summary.get('per_frame_csv', '')}")

    except Exception as exc:
        log_exception(logger, "Video inference failed", exc)
        raise


if __name__ == "__main__":
    main()
