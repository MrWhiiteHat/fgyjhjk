"""CLI entrypoint for Grad-CAM and saliency explanation generation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from evaluation.explainability.explain_runner import ExplainabilityRunner
from evaluation.inference.predictor import Predictor
from evaluation.inference.preprocessing_adapter import InferencePreprocessor
from evaluation.utils.helpers import load_yaml
from evaluation.utils.io import ensure_output_structure, save_dict_json
from evaluation.utils.logger import get_logger, log_exception


def parse_args() -> argparse.Namespace:
    """Parse command-line args for explanation generation."""
    parser = argparse.ArgumentParser(description="Generate Grad-CAM and saliency explainability outputs")
    parser.add_argument("--config", type=str, default="evaluation/configs/eval_config.yaml", help="Evaluation config path")
    parser.add_argument("--image", type=str, default="", help="Single image path for explanation")
    parser.add_argument("--input-csv", type=str, default="", help="Optional CSV with filepath column")
    parser.add_argument("--top-k", type=int, default=10, help="Max rows from input CSV to process")
    parser.add_argument("--checkpoint", type=str, default="", help="Optional checkpoint override")
    parser.add_argument("--exported-model", type=str, default="", help="Optional exported model override")
    return parser.parse_args()


def main() -> None:
    """Execute explainability generation for one or many images."""
    args = parse_args()
    config = load_yaml(args.config)

    if args.checkpoint:
        config["checkpoint_path"] = args.checkpoint
    if args.exported_model:
        config["exported_model_path"] = args.exported_model

    output_dirs = ensure_output_structure(config.get("output_dir", "evaluation/outputs"))
    logger, _ = get_logger(
        name="generate_explanations",
        log_dir=output_dirs["reports"],
        log_level=str(config.get("log_level", "INFO")),
        log_filename="generate_explanations.log",
    )

    try:
        preprocessor = InferencePreprocessor(config=config)
        predictor = Predictor(config=config, logger=logger)
        runner = ExplainabilityRunner(
            predictor=predictor,
            preprocessor=preprocessor,
            config=config,
            logger=logger,
        )

        targets: List[str] = []
        if args.image:
            targets.append(args.image)

        if args.input_csv:
            csv_path = Path(args.input_csv)
            if not csv_path.exists() or not csv_path.is_file():
                raise FileNotFoundError(f"Input CSV does not exist: {csv_path}")
            table = pd.read_csv(csv_path)
            if "filepath" not in table.columns:
                raise KeyError("Input CSV must contain 'filepath' column")
            csv_targets = table["filepath"].astype(str).tolist()[: int(args.top_k)]
            targets.extend(csv_targets)

        if not targets:
            raise ValueError("Provide --image or --input-csv to generate explanations")

        records = []
        for path in targets:
            prediction = predictor.predict_image_path(path, preprocessor=preprocessor)
            label_idx = int(prediction.get("predicted_label_index", 1)) if prediction.get("status") == "ok" else 1
            explanation = runner.explain_image_path(path, predicted_label_index=label_idx)

            records.append(
                {
                    "filepath": str(path),
                    "prediction_status": prediction.get("status", "error"),
                    "predicted_label": prediction.get("predicted_label", ""),
                    "predicted_probability": float(prediction.get("predicted_probability", 0.0)),
                    "explanation_status": explanation.get("status", "error"),
                    "gradcam": explanation.get("gradcam", {}),
                    "saliency": explanation.get("saliency", {}),
                    "error_message": explanation.get("error_message", ""),
                }
            )

        output_json = Path(config.get("output_dir", "evaluation/outputs")) / "explainability" / "explanations_summary.json"
        save_dict_json({"records": records}, output_json)

        print("Explainability Generation Complete")
        print("---------------------------------")
        print(f"Samples Processed: {len(records)}")
        print(f"Summary JSON: {output_json.as_posix()}")

    except Exception as exc:
        log_exception(logger, "Explanation generation failed", exc)
        raise


if __name__ == "__main__":
    main()
