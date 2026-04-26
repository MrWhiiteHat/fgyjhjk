"""CLI entrypoint for recursive folder inference."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from evaluation.inference.folder_inference import run_folder_inference
from evaluation.inference.predictor import Predictor
from evaluation.inference.preprocessing_adapter import InferencePreprocessor
from evaluation.utils.helpers import load_yaml
from evaluation.utils.io import ensure_output_structure
from evaluation.utils.logger import get_logger, log_exception


def parse_args() -> argparse.Namespace:
    """Parse command-line args for folder inference."""
    parser = argparse.ArgumentParser(description="Run batch folder inference")
    parser.add_argument("--config", type=str, default="evaluation/configs/eval_config.yaml", help="Evaluation config path")
    parser.add_argument("--input-dir", type=str, required=True, help="Input folder path")
    parser.add_argument("--batch-size", type=int, default=0, help="Optional batch size override")
    parser.add_argument("--checkpoint", type=str, default="", help="Optional checkpoint override")
    parser.add_argument("--exported-model", type=str, default="", help="Optional exported model override")
    return parser.parse_args()


def main() -> None:
    """Execute folder inference pipeline."""
    args = parse_args()
    config = load_yaml(args.config)

    if args.batch_size > 0:
        config["batch_size"] = int(args.batch_size)
    if args.checkpoint:
        config["checkpoint_path"] = args.checkpoint
    if args.exported_model:
        config["exported_model_path"] = args.exported_model

    output_dirs = ensure_output_structure(config.get("output_dir", "evaluation/outputs"))
    logger, _ = get_logger(
        name="infer_folder",
        log_dir=output_dirs["reports"],
        log_level=str(config.get("log_level", "INFO")),
        log_filename="infer_folder.log",
    )

    try:
        preprocessor = InferencePreprocessor(config=config)
        predictor = Predictor(config=config, logger=logger)

        payload = run_folder_inference(
            input_dir=args.input_dir,
            predictor=predictor,
            preprocessor=preprocessor,
            config=config,
            logger=logger,
        )

        summary = payload["summary"]
        print("Folder Inference Complete")
        print("-------------------------")
        print(f"Input Dir: {summary.get('input_dir', '')}")
        print(f"Total Files: {summary.get('total_files', 0)}")
        print(f"Processed: {summary.get('total_processed', 0)}")
        print(f"REAL Predictions: {summary.get('total_real_predictions', 0)}")
        print(f"FAKE Predictions: {summary.get('total_fake_predictions', 0)}")
        print(f"Average Confidence: {float(summary.get('average_confidence', 0.0)):.4f}")
        print(f"Fastest Inference: {float(summary.get('fastest_inference_ms', 0.0)):.2f} ms")
        print(f"Slowest Inference: {float(summary.get('slowest_inference_ms', 0.0)):.2f} ms")
        print(f"Predictions CSV: {summary.get('predictions_csv', '')}")

    except Exception as exc:
        log_exception(logger, "Folder inference failed", exc)
        raise


if __name__ == "__main__":
    main()
