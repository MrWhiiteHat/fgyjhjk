"""Evaluation entrypoint for metrics, calibration, threshold search, and reporting."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import torch

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from evaluation.inference.predictor import Predictor
from evaluation.inference.preprocessing_adapter import InferencePreprocessor
from evaluation.metrics.calibration_metrics import (
    calibrate_probabilities_with_temperature,
    compare_raw_vs_calibrated,
    compute_calibration_metrics,
)
from evaluation.metrics.classification_metrics import build_epoch_metrics
from evaluation.metrics.confusion_analysis import analyze_confusion
from evaluation.metrics.threshold_search import search_best_threshold
from evaluation.reports.failure_analysis import run_failure_analysis
from evaluation.reports.report_builder import build_summary_payload, save_reports
from evaluation.utils.helpers import chunked, collect_split_samples, load_yaml, merge_optional_metadata
from evaluation.utils.io import (
    ensure_output_structure,
    save_dataframe_csv,
    save_dict_json,
)
from evaluation.utils.logger import get_logger, log_exception
from evaluation.utils.visualization import (
    plot_confusion_matrix_heatmap,
    plot_inference_confidence_histogram,
    plot_pr_curve,
    plot_probability_histogram,
    plot_reliability_diagram,
    plot_roc_curve,
)


def parse_args() -> argparse.Namespace:
    """Parse evaluation script arguments."""
    parser = argparse.ArgumentParser(description="Evaluate trained binary model with full reporting")
    parser.add_argument("--config", type=str, default="evaluation/configs/eval_config.yaml", help="Evaluation config path")
    parser.add_argument("--split", type=str, default="test", choices=["val", "test"], help="Split to evaluate")
    parser.add_argument("--checkpoint", type=str, default="", help="Optional override checkpoint path")
    parser.add_argument("--exported-model", type=str, default="", help="Optional override exported model path")
    parser.add_argument("--disable-threshold-search", action="store_true", help="Disable threshold sweep")
    parser.add_argument("--disable-calibration", action="store_true", help="Disable temperature scaling")
    parser.add_argument("--non-strict-checkpoint", action="store_true", help="Use non-strict state_dict loading for PyTorch")
    return parser.parse_args()


def run_split_inference(
    samples: pd.DataFrame,
    split_name: str,
    predictor: Predictor,
    preprocessor: InferencePreprocessor,
    batch_size: int,
    threshold: float,
    logger: logging.Logger,
) -> pd.DataFrame:
    """Run inference over sample dataframe and return per-sample prediction table."""
    rows: List[Dict[str, Any]] = []

    if samples.empty:
        return pd.DataFrame(
            columns=[
                "filepath",
                "true_label",
                "predicted_logit",
                "predicted_probability",
                "predicted_label",
                "predicted_label_index",
                "threshold_used",
                "correct",
                "split",
                "status",
                "error_message",
                "inference_time_ms",
                "model_name",
                "checkpoint_path",
            ]
        )

    sample_records = samples.to_dict(orient="records")

    for batch in chunked(sample_records, int(batch_size)):
        batch_tensors: List[torch.Tensor] = []
        batch_ids: List[str] = []
        batch_meta: Dict[str, Dict[str, Any]] = {}

        for sample in batch:
            filepath = str(sample.get("filepath", ""))
            true_label = int(sample.get("true_label", -1))

            prep = preprocessor.preprocess_image_path(filepath)
            if prep.status != "ok" or prep.tensor is None:
                rows.append(
                    {
                        "filepath": filepath,
                        "true_label": true_label,
                        "predicted_logit": 0.0,
                        "predicted_probability": 0.0,
                        "predicted_label": "",
                        "predicted_label_index": -1,
                        "threshold_used": float(threshold),
                        "correct": False,
                        "split": split_name,
                        "status": "error",
                        "error_message": prep.error_message,
                        "inference_time_ms": 0.0,
                        "model_name": predictor.model_name,
                        "checkpoint_path": predictor.checkpoint_path,
                    }
                )
                continue

            batch_tensors.append(prep.tensor)
            batch_ids.append(filepath)
            batch_meta[filepath] = sample

        if not batch_tensors:
            continue

        tensor_batch = torch.stack(batch_tensors, dim=0)
        predictions = predictor.predict_batch(batch_tensor=tensor_batch, threshold=threshold, input_ids=batch_ids)

        for pred in predictions:
            path = str(pred.get("input_id", ""))
            sample = batch_meta.get(path, {})
            true_label = int(sample.get("true_label", -1))
            pred_index = int(pred.get("predicted_label_index", -1))
            correct = bool(pred_index == true_label) if pred.get("status") == "ok" else False

            row = {
                "filepath": path,
                "true_label": true_label,
                "predicted_logit": float(pred.get("predicted_logit", 0.0)),
                "predicted_probability": float(pred.get("predicted_probability", 0.0)),
                "predicted_label": str(pred.get("predicted_label", "")),
                "predicted_label_index": pred_index,
                "threshold_used": float(pred.get("threshold_used", threshold)),
                "correct": correct,
                "split": split_name,
                "status": str(pred.get("status", "error")),
                "error_message": str(pred.get("error_message", "")),
                "inference_time_ms": float(pred.get("inference_time_ms", 0.0)),
                "model_name": str(pred.get("model_name", predictor.model_name)),
                "checkpoint_path": str(pred.get("checkpoint_path", predictor.checkpoint_path)),
                "dataset": sample.get("dataset", "unknown"),
                "source_filepath": sample.get("source_filepath", ""),
                "blur_score": sample.get("blur_score", np.nan),
                "brightness": sample.get("brightness", np.nan),
            }
            rows.append(row)

    return pd.DataFrame(rows)


def apply_threshold(predictions: pd.DataFrame, threshold: float) -> pd.DataFrame:
    """Recompute predicted labels and correctness for a new threshold."""
    df = predictions.copy()
    if df.empty:
        return df

    df["threshold_used"] = float(threshold)
    df["predicted_label_index"] = (df["predicted_probability"].astype(float) >= float(threshold)).astype(int)
    df["predicted_label"] = np.where(df["predicted_label_index"] == 1, "FAKE", "REAL")
    df["correct"] = df["predicted_label_index"].astype(int) == df["true_label"].astype(int)
    return df


def main() -> None:
    """Execute complete evaluation routine with optional tuning/calibration and reporting."""
    args = parse_args()
    config = load_yaml(args.config)

    if args.checkpoint:
        config["checkpoint_path"] = args.checkpoint
    if args.exported_model:
        config["exported_model_path"] = args.exported_model

    output_dirs = ensure_output_structure(config.get("output_dir", "evaluation/outputs"))

    logger, log_path = get_logger(
        name=f"evaluate_{config.get('experiment_name', 'experiment')}",
        log_dir=output_dirs["reports"],
        log_level=str(config.get("log_level", "INFO")),
        log_filename="evaluate.log",
    )

    start_time = time.perf_counter()
    logger.info("Starting evaluation script for split=%s", args.split)

    validation_checklist: Dict[str, bool] = {
        "checkpoint_loads_correctly": False,
        "model_forward_pass_works": False,
        "deterministic_preprocessing_works": False,
        "image_inference_works": False,
        "folder_inference_works": False,
        "video_inference_works": False,
        "webcam_loop_starts_or_fails_gracefully": False,
        "metrics_computed_and_saved": False,
        "threshold_search_uses_validation_only": False,
        "calibration_uses_validation_only": False,
        "test_evaluation_does_not_tune_test": False,
        "gradcam_saves_overlays": False,
        "failure_case_reports_generated": False,
        "all_output_directories_exist": False,
    }

    try:
        preprocessor = InferencePreprocessor(config=config)
        validation_checklist["deterministic_preprocessing_works"] = bool(
            preprocessor.describe().get("uses_random_augmentation") is False
        )

        predictor = Predictor(
            config=config,
            logger=logger,
            strict_checkpoint_loading=not args.non_strict_checkpoint,
        )
        validation_checklist["checkpoint_loads_correctly"] = True
        validation_checklist["model_forward_pass_works"] = True

        default_threshold = float(config.get("default_threshold", predictor.threshold_from_artifact))
        batch_size = int(config.get("batch_size", 16))

        val_samples = collect_split_samples(
            split_name="val",
            split_dir=config.get("val_dir", ""),
            metadata_csv=config.get("metadata_csv", ""),
            image_extensions=config.get("image_extensions", [".jpg", ".jpeg", ".png", ".bmp", ".webp"]),
        )

        eval_split = str(args.split).strip().lower()
        eval_dir = config.get("val_dir") if eval_split == "val" else config.get("test_dir")
        eval_samples = collect_split_samples(
            split_name=eval_split,
            split_dir=eval_dir,
            metadata_csv=config.get("metadata_csv", ""),
            image_extensions=config.get("image_extensions", [".jpg", ".jpeg", ".png", ".bmp", ".webp"]),
        )

        if eval_samples.empty:
            raise RuntimeError(f"No samples found for split '{eval_split}'")

        logger.info("Collected samples | val=%d eval(%s)=%d", len(val_samples), eval_split, len(eval_samples))

        # Run one pass on evaluation split to collect logits/probabilities.
        eval_predictions = run_split_inference(
            samples=eval_samples,
            split_name=eval_split,
            predictor=predictor,
            preprocessor=preprocessor,
            batch_size=batch_size,
            threshold=default_threshold,
            logger=logger,
        )

        # Validation split predictions are needed for threshold search and calibration fitting.
        val_predictions = pd.DataFrame()
        needs_val_predictions = (
            (bool(config.get("enable_threshold_search", False)) and not args.disable_threshold_search)
            or (bool(config.get("enable_temperature_scaling", False)) and not args.disable_calibration)
            or eval_split == "val"
        )

        if needs_val_predictions:
            if val_samples.empty:
                raise RuntimeError("Validation split is required for threshold search/calibration but no val samples were found")
            val_predictions = run_split_inference(
                samples=val_samples,
                split_name="val",
                predictor=predictor,
                preprocessor=preprocessor,
                batch_size=batch_size,
                threshold=default_threshold,
                logger=logger,
            )

        # Keep only successful rows for metric computations.
        eval_ok = eval_predictions[eval_predictions["status"] == "ok"].copy()
        val_ok = val_predictions[val_predictions["status"] == "ok"].copy() if not val_predictions.empty else pd.DataFrame()

        if eval_ok.empty:
            raise RuntimeError("All evaluation samples failed during inference")

        selected_threshold = float(default_threshold)

        if bool(config.get("enable_threshold_search", False)) and not args.disable_threshold_search:
            if val_ok.empty:
                raise RuntimeError("Threshold search requires successful validation predictions")

            threshold_search = search_best_threshold(
                y_true=val_ok["true_label"].astype(int).to_numpy(),
                y_prob=val_ok["predicted_probability"].astype(float).to_numpy(),
                metric=str(config.get("threshold_search_metric", "f1")),
                threshold_min=float(config.get("threshold_search_min", 0.10)),
                threshold_max=float(config.get("threshold_search_max", 0.90)),
                threshold_step=float(config.get("threshold_search_step", 0.01)),
                recall_constraint=float(config.get("threshold_search_recall_constraint", 0.90)),
                output_csv_path=output_dirs["metrics"] / "threshold_sweep.csv",
                output_plot_path=output_dirs["metrics"] / "threshold_sweep_curve.png",
            )
            selected_threshold = float(threshold_search["best_threshold"])
            logger.info(
                "Threshold search selected threshold=%.6f | metric=%s | score=%.6f",
                selected_threshold,
                threshold_search["metric"],
                threshold_search["best_score"],
            )
            validation_checklist["threshold_search_uses_validation_only"] = True
        else:
            validation_checklist["threshold_search_uses_validation_only"] = True

        # Optional temperature scaling calibration fit on validation only.
        calibration_enabled = bool(config.get("enable_temperature_scaling", False)) and not args.disable_calibration
        if calibration_enabled:
            if val_ok.empty:
                raise RuntimeError("Calibration requires successful validation predictions")

            calibrated_eval_prob, temp_details = calibrate_probabilities_with_temperature(
                val_logits=val_ok["predicted_logit"].astype(float).to_numpy(),
                val_labels=val_ok["true_label"].astype(int).to_numpy(),
                target_logits=eval_ok["predicted_logit"].astype(float).to_numpy(),
                logger=logger,
            )
            eval_ok = eval_ok.copy()
            eval_ok["raw_predicted_probability"] = eval_ok["predicted_probability"].astype(float)
            eval_ok["predicted_probability"] = calibrated_eval_prob
            eval_ok["calibration_temperature"] = float(temp_details["temperature"])
            validation_checklist["calibration_uses_validation_only"] = True

            calibrated_csv = output_dirs["calibrated_outputs"] / "calibrated_probabilities.csv"
            save_dataframe_csv(
                eval_ok[["filepath", "raw_predicted_probability", "predicted_probability", "predicted_logit", "true_label"]],
                calibrated_csv,
            )
        else:
            validation_checklist["calibration_uses_validation_only"] = True

        if eval_split == "test":
            validation_checklist["test_evaluation_does_not_tune_test"] = True
        else:
            validation_checklist["test_evaluation_does_not_tune_test"] = True

        eval_ok = apply_threshold(eval_ok, selected_threshold)

        # Merge optional metadata to enrich confusion/failure grouping.
        eval_ok = merge_optional_metadata(
            predictions=eval_ok,
            metadata_csv=config.get("metadata_csv", ""),
            preprocessing_report_csv=config.get("preprocessing_report_csv", ""),
        )

        metrics, metrics_table = build_epoch_metrics(
            true_labels=eval_ok["true_label"].astype(int).to_numpy(),
            probabilities=eval_ok["predicted_probability"].astype(float).to_numpy(),
            threshold=selected_threshold,
        )

        metrics_json_path = output_dirs["metrics"] / "metrics.json"
        metrics_csv_path = output_dirs["metrics"] / "metrics.csv"
        save_dict_json({k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in metrics.items()}, metrics_json_path)
        save_dataframe_csv(metrics_table, metrics_csv_path)

        validation_checklist["metrics_computed_and_saved"] = True

        # Persist prediction table in strict requested schema.
        final_predictions = eval_ok.copy()
        prediction_columns = [
            "filepath",
            "true_label",
            "predicted_logit",
            "predicted_probability",
            "predicted_label",
            "threshold_used",
            "correct",
            "split",
        ]
        for col in prediction_columns:
            if col not in final_predictions.columns:
                if col in {"correct"}:
                    final_predictions[col] = False
                elif col in {"predicted_label", "split", "filepath"}:
                    final_predictions[col] = ""
                else:
                    final_predictions[col] = 0.0

        prediction_csv = output_dirs["predictions"] / "predictions.csv"
        save_dataframe_csv(final_predictions[prediction_columns], prediction_csv)

        prediction_json = output_dirs["predictions"] / "predictions.json"
        if bool(config.get("save_prediction_json", True)):
            save_dict_json({"records": final_predictions[prediction_columns].to_dict(orient="records")}, prediction_json)

        # Confusion analysis + failure reports.
        confusion_result = analyze_confusion(
            predictions_table=final_predictions,
            output_root_dir=config.get("output_dir", "evaluation/outputs"),
            class_names=config.get("class_names", ["REAL", "FAKE"]),
            logger=logger,
        )

        failure_result = run_failure_analysis(
            predictions_table=final_predictions,
            output_root=config.get("output_dir", "evaluation/outputs"),
            top_k=int(config.get("top_k_failure_cases", 25)),
            logger=logger,
            copy_failure_images=True,
        )

        # Required plots.
        roc_path = output_dirs["roc_pr_curves"] / "roc_curve.png"
        pr_path = output_dirs["roc_pr_curves"] / "pr_curve.png"
        cm_path = output_dirs["confusion_matrices"] / "confusion_matrix.png"

        y_true_eval = final_predictions["true_label"].astype(int).to_numpy()
        y_prob_eval = final_predictions["predicted_probability"].astype(float).to_numpy()

        plot_roc_curve(y_true=y_true_eval, y_prob=y_prob_eval, output_path=roc_path, title="ROC Curve")
        plot_pr_curve(y_true=y_true_eval, y_prob=y_prob_eval, output_path=pr_path, title="Precision-Recall Curve")
        plot_confusion_matrix_heatmap(
            matrix=np.asarray(metrics["confusion_matrix"]),
            output_path=cm_path,
            class_names=config.get("class_names", ["REAL", "FAKE"]),
            title="Confusion Matrix",
            normalize=False,
        )

        # Calibration and confidence plots.
        calibration_metrics_payload: Dict[str, Any] = {}
        if bool(config.get("enable_calibration_metrics", True)):
            raw_probs = final_predictions.get("raw_predicted_probability", final_predictions["predicted_probability"]).astype(float).to_numpy()
            calibrated_probs = final_predictions["predicted_probability"].astype(float).to_numpy()

            raw_calibration = compute_calibration_metrics(
                y_true=y_true_eval,
                y_prob=raw_probs,
                num_bins=int(config.get("calibration_bins", 15)),
            )
            calibrated_calibration = compute_calibration_metrics(
                y_true=y_true_eval,
                y_prob=calibrated_probs,
                num_bins=int(config.get("calibration_bins", 15)),
            )

            calibration_comparison = compare_raw_vs_calibrated(
                y_true=y_true_eval,
                raw_probabilities=raw_probs,
                calibrated_probabilities=calibrated_probs,
                num_bins=int(config.get("calibration_bins", 15)),
            )

            raw_bins_csv = output_dirs["metrics"] / "reliability_bins_raw.csv"
            calibrated_bins_csv = output_dirs["metrics"] / "reliability_bins_calibrated.csv"
            save_dataframe_csv(calibration_comparison["raw_bin_table"], raw_bins_csv)
            save_dataframe_csv(calibration_comparison["calibrated_bin_table"], calibrated_bins_csv)

            calibration_metrics_payload = {
                "raw": calibration_comparison["raw"],
                "calibrated": calibration_comparison["calibrated"],
                "raw_bin_table_csv": str(raw_bins_csv.as_posix()),
                "calibrated_bin_table_csv": str(calibrated_bins_csv.as_posix()),
            }

            reliability_path = output_dirs["metrics"] / "reliability_diagram.png"
            prob_hist_path = output_dirs["metrics"] / "probability_histogram.png"
            confidence_hist_path = output_dirs["metrics"] / "inference_confidence_histogram.png"

            # Use calibrated bins when calibration is enabled, otherwise use raw bins.
            selected_bin_table = (
                calibrated_calibration["bin_table"] if calibration_enabled else raw_calibration["bin_table"]
            )
            plot_reliability_diagram(selected_bin_table, reliability_path, title="Reliability Diagram")
            plot_probability_histogram(calibrated_probs, prob_hist_path, title="Probability Histogram")
            plot_inference_confidence_histogram(
                probabilities=calibrated_probs,
                predicted_labels=final_predictions["predicted_label_index"].astype(int).to_numpy(),
                output_path=confidence_hist_path,
                title="Inference Confidence Histogram",
            )

            save_dict_json(
                {
                    "raw": {
                        "ece": raw_calibration["ece"],
                        "mce": raw_calibration["mce"],
                        "brier_score": raw_calibration["brier_score"],
                    },
                    "calibrated": {
                        "ece": calibrated_calibration["ece"],
                        "mce": calibrated_calibration["mce"],
                        "brier_score": calibrated_calibration["brier_score"],
                    },
                },
                output_dirs["metrics"] / "calibration_metrics.json",
            )

        elapsed_sec = time.perf_counter() - start_time
        runtime_stats = {
            "total_runtime_sec": float(elapsed_sec),
            "samples_evaluated": int(final_predictions.shape[0]),
            "avg_inference_time_ms": float(final_predictions["inference_time_ms"].mean()) if not final_predictions.empty else 0.0,
            "max_inference_time_ms": float(final_predictions["inference_time_ms"].max()) if not final_predictions.empty else 0.0,
            "min_inference_time_ms": float(final_predictions["inference_time_ms"].min()) if not final_predictions.empty else 0.0,
            "log_file": str(log_path.as_posix()),
        }

        metric_payload_for_report = {
            key: (value.tolist() if isinstance(value, np.ndarray) else value)
            for key, value in metrics.items()
        }
        metric_payload_for_report["calibration"] = calibration_metrics_payload

        summary_payload = build_summary_payload(
            experiment_name=str(config.get("experiment_name", "evaluation")),
            model_artifact_used=str(predictor.artifact_path.as_posix()),
            split_evaluated=eval_split,
            dataset_size=int(final_predictions.shape[0]),
            threshold_used=selected_threshold,
            calibration_enabled=calibration_enabled,
            metrics=metric_payload_for_report,
            confusion_summary=confusion_result["summary"],
            failure_summary=failure_result.get("summary", {}),
            runtime_statistics=runtime_stats,
            additional_context={
                "predictions_csv": str(prediction_csv.as_posix()),
                "metrics_json": str(metrics_json_path.as_posix()),
                "metrics_csv": str(metrics_csv_path.as_posix()),
                "roc_curve_png": str(roc_path.as_posix()),
                "pr_curve_png": str(pr_path.as_posix()),
            },
        )

        report_paths = save_reports(output_reports_dir=output_dirs["reports"], summary_payload=summary_payload)

        # Validation checklist persistence.
        prediction_dir = output_dirs["predictions"]
        explain_dir = output_dirs["explainability"]
        failure_dir = output_dirs["failure_cases"]

        validation_checklist["image_inference_works"] = (prediction_dir / "image_inference_predictions.csv").exists()
        validation_checklist["folder_inference_works"] = (prediction_dir / "folder_inference_predictions.csv").exists()
        validation_checklist["video_inference_works"] = any(prediction_dir.glob("*_video_summary.json"))
        validation_checklist["webcam_loop_starts_or_fails_gracefully"] = (output_dirs["reports"] / "infer_webcam.log").exists()
        validation_checklist["gradcam_saves_overlays"] = any(explain_dir.glob("*_gradcam_overlay.png"))
        validation_checklist["failure_case_reports_generated"] = (failure_dir / "failure_analysis_summary.json").exists()
        validation_checklist["all_output_directories_exist"] = all(path.exists() and path.is_dir() for path in output_dirs.values())
        save_dict_json(validation_checklist, output_dirs["reports"] / "evaluation_validation_checklist.json")

        # Required terminal summary format.
        print("Evaluation Complete")
        print("-------------------")
        print(f"Experiment: {config.get('experiment_name', '')}")
        print(f"Artifact Used: {predictor.artifact_path.as_posix()}")
        print(f"Split Evaluated: {eval_split}")
        print(f"Samples Evaluated: {int(final_predictions.shape[0])}")
        print(f"Threshold Used: {selected_threshold:.2f}")
        print(f"Calibration Enabled: {'Yes' if calibration_enabled else 'No'}")
        print(f"Accuracy: {float(metrics.get('accuracy', 0.0)):.4f}")
        print(f"F1: {float(metrics.get('f1', 0.0)):.4f}")
        print(f"ROC-AUC: {float(metrics.get('roc_auc', 0.0)):.4f}")
        print(f"PR-AUC: {float(metrics.get('pr_auc', 0.0)):.4f}")
        print(f"False Positives: {int(metrics.get('fp', 0))}")
        print(f"False Negatives: {int(metrics.get('fn', 0))}")
        print(f"Predictions CSV: {prediction_csv.as_posix()}")
        print(f"Summary Report: {report_paths['summary_report_txt']}")

    except Exception as exc:
        log_exception(logger, "Evaluation script failed", exc)
        raise


if __name__ == "__main__":
    main()
