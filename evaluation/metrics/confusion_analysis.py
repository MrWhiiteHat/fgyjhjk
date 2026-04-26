"""Confusion-matrix analysis and failure case grouping utilities."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Sequence

import numpy as np
import pandas as pd

from evaluation.utils.io import save_dataframe_csv, save_dict_json
from evaluation.utils.visualization import plot_confusion_matrix_heatmap


def _ensure_predicted_index_column(table: pd.DataFrame) -> pd.DataFrame:
    """Ensure predicted label index column exists for confusion analysis."""
    df = table.copy()
    if "predicted_label_index" in df.columns:
        return df

    if "predicted_label" not in df.columns:
        raise KeyError("Predictions table must contain predicted_label or predicted_label_index")

    pred_text = df["predicted_label"].astype(str).str.upper()
    df["predicted_label_index"] = np.where(pred_text == "FAKE", 1, 0)
    return df


def _add_optional_buckets(df: pd.DataFrame) -> pd.DataFrame:
    """Add confidence/brightness/blur buckets when source columns are available."""
    output = df.copy()

    if "predicted_probability" in output.columns:
        output["confidence_bucket"] = pd.cut(
            output["predicted_probability"].astype(float),
            bins=[-1e-9, 0.2, 0.4, 0.6, 0.8, 1.0],
            labels=["very_low", "low", "mid", "high", "very_high"],
            include_lowest=True,
        )
    else:
        output["confidence_bucket"] = "unknown"

    brightness_col = "brightness"
    if brightness_col not in output.columns and "brightness_score" in output.columns:
        brightness_col = "brightness_score"

    if brightness_col in output.columns:
        output["brightness_bucket"] = pd.cut(
            output[brightness_col].astype(float),
            bins=[-np.inf, 60, 100, 160, 220, np.inf],
            labels=["very_dark", "dark", "normal", "bright", "very_bright"],
        )
    else:
        output["brightness_bucket"] = "unknown"

    blur_col = "blur_score"
    if blur_col not in output.columns and "blur" in output.columns:
        blur_col = "blur"

    if blur_col in output.columns:
        output["blur_bucket"] = pd.cut(
            output[blur_col].astype(float),
            bins=[-np.inf, 20, 60, 120, np.inf],
            labels=["very_blurry", "blurry", "moderate", "sharp"],
        )
    else:
        output["blur_bucket"] = "unknown"

    if "split" not in output.columns:
        output["split"] = "unknown"

    if "dataset" not in output.columns:
        if "dataset_source" in output.columns:
            output["dataset"] = output["dataset_source"]
        elif "source_dataset" in output.columns:
            output["dataset"] = output["source_dataset"]
        else:
            output["dataset"] = "unknown"

    return output


def analyze_confusion(
    predictions_table: pd.DataFrame,
    output_root_dir: str | Path,
    class_names: Sequence[str],
    logger: logging.Logger,
) -> Dict[str, Any]:
    """Compute confusion analysis, grouped failures, and matrix visualizations."""
    if predictions_table.empty:
        raise ValueError("Predictions table is empty; confusion analysis requires data")

    output_root = Path(output_root_dir)
    cm_dir = output_root / "confusion_matrices"
    failure_dir = output_root / "failure_cases"
    cm_dir.mkdir(parents=True, exist_ok=True)
    failure_dir.mkdir(parents=True, exist_ok=True)

    table = _ensure_predicted_index_column(predictions_table)
    table = _add_optional_buckets(table)

    if "true_label" not in table.columns:
        raise KeyError("Predictions table must contain true_label column")

    true_labels = table["true_label"].astype(int).to_numpy()
    pred_labels = table["predicted_label_index"].astype(int).to_numpy()

    tp = int(np.sum((true_labels == 1) & (pred_labels == 1)))
    tn = int(np.sum((true_labels == 0) & (pred_labels == 0)))
    fp = int(np.sum((true_labels == 0) & (pred_labels == 1)))
    fn = int(np.sum((true_labels == 1) & (pred_labels == 0)))
    cm = np.asarray([[tn, fp], [fn, tp]], dtype=np.int64)

    fp_table = table[(table["true_label"].astype(int) == 0) & (table["predicted_label_index"].astype(int) == 1)].copy()
    fn_table = table[(table["true_label"].astype(int) == 1) & (table["predicted_label_index"].astype(int) == 0)].copy()

    fp_csv = failure_dir / "false_positives.csv"
    fn_csv = failure_dir / "false_negatives.csv"
    save_dataframe_csv(fp_table, fp_csv)
    save_dataframe_csv(fn_table, fn_csv)

    # Group failures by required dimensions.
    failure_table = pd.concat([fp_table, fn_table], axis=0, ignore_index=True)
    grouped_paths: Dict[str, str] = {}

    if not failure_table.empty:
        group_specs = {
            "by_split": ["split"],
            "by_dataset": ["dataset"],
            "by_brightness_bucket": ["brightness_bucket"],
            "by_blur_bucket": ["blur_bucket"],
            "by_confidence_bucket": ["confidence_bucket"],
            "by_split_dataset": ["split", "dataset"],
        }

        for group_name, columns in group_specs.items():
            grouped = (
                failure_table.groupby(columns, dropna=False)
                .size()
                .reset_index(name="count")
                .sort_values(by="count", ascending=False)
            )
            group_path = failure_dir / f"failure_groups_{group_name}.csv"
            save_dataframe_csv(grouped, group_path)
            grouped_paths[group_name] = str(group_path.as_posix())

    raw_cm_path = cm_dir / "confusion_matrix_raw.png"
    norm_cm_path = cm_dir / "confusion_matrix_normalized.png"

    plot_confusion_matrix_heatmap(
        matrix=cm,
        output_path=raw_cm_path,
        class_names=class_names,
        title="Confusion Matrix",
        normalize=False,
    )
    plot_confusion_matrix_heatmap(
        matrix=cm,
        output_path=norm_cm_path,
        class_names=class_names,
        title="Confusion Matrix",
        normalize=True,
    )

    summary = {
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "false_positives_csv": str(fp_csv.as_posix()),
        "false_negatives_csv": str(fn_csv.as_posix()),
        "confusion_matrix_raw_png": str(raw_cm_path.as_posix()),
        "confusion_matrix_normalized_png": str(norm_cm_path.as_posix()),
        "grouped_failure_tables": grouped_paths,
    }

    save_dict_json(summary, cm_dir / "confusion_analysis_summary.json")
    logger.info("Confusion analysis complete | TP=%d TN=%d FP=%d FN=%d", tp, tn, fp, fn)

    return {
        "summary": summary,
        "fp_table": fp_table,
        "fn_table": fn_table,
        "confusion_matrix": cm,
    }
