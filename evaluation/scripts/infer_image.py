"""CLI entrypoint for single image inference."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from evaluation.explainability.explain_runner import ExplainabilityRunner
from evaluation.inference.image_inference import run_image_inference
from evaluation.inference.predictor import Predictor
from evaluation.inference.preprocessing_adapter import InferencePreprocessor
from evaluation.utils.helpers import load_yaml
from evaluation.utils.io import ensure_output_structure
from evaluation.utils.logger import get_logger, log_exception


def parse_args() -> argparse.Namespace:
    """Parse command-line args for image inference."""
    parser = argparse.ArgumentParser(description="Run single image inference")
    parser.add_argument("--config", type=str, default="evaluation/configs/eval_config.yaml", help="Evaluation config path")
    parser.add_argument("--image", type=str, required=True, help="Input image path")
    parser.add_argument("--checkpoint", type=str, default="", help="Optional checkpoint override")
    parser.add_argument("--exported-model", type=str, default="", help="Optional exported model override")
    return parser.parse_args()


def main() -> None:
    """Execute image inference pipeline."""
    args = parse_args()
    config = load_yaml(args.config)

    if args.checkpoint:
        config["checkpoint_path"] = args.checkpoint
    if args.exported_model:
        config["exported_model_path"] = args.exported_model

    output_dirs = ensure_output_structure(config.get("output_dir", "evaluation/outputs"))
    logger, _ = get_logger(
        name="infer_image",
        log_dir=output_dirs["reports"],
        log_level=str(config.get("log_level", "INFO")),
        log_filename="infer_image.log",
    )

    try:
        preprocessor = InferencePreprocessor(config=config)
        predictor = Predictor(config=config, logger=logger)

        explain_runner = None
        if bool(config.get("enable_gradcam", True)) or bool(config.get("enable_saliency", True)):
            explain_runner = ExplainabilityRunner(
                predictor=predictor,
                preprocessor=preprocessor,
                config=config,
                logger=logger,
            )

        output = run_image_inference(
            image_path=args.image,
            predictor=predictor,
            preprocessor=preprocessor,
            config=config,
            logger=logger,
            explain_runner=explain_runner,
        )

        if output.get("status") != "ok" or output.get("result") is None:
            raise RuntimeError(output.get("error_message", "Image inference failed"))

        result = output["result"]

        print("Image Inference Complete")
        print("------------------------")
        print(f"File: {args.image}")
        print(f"Predicted Label: {result.get('predicted_label', '')}")
        print(f"Probability: {float(result.get('predicted_probability', 0.0)):.4f}")
        print(f"Threshold Used: {float(result.get('threshold_used', 0.5)):.2f}")
        print(f"Inference Time: {float(result.get('inference_time_ms', 0.0)):.1f} ms")

    except Exception as exc:
        log_exception(logger, "Image inference failed", exc)
        raise


if __name__ == "__main__":
    main()
