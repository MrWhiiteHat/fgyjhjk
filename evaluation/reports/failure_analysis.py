"""Failure-case analysis utilities for false positives/negatives and hard samples."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

import pandas as pd

from evaluation.utils.io import copy_file_safe, save_dataframe_csv, save_dict_json, sanitize_filename


def run_failure_analysis(
    predictions_table: pd.DataFrame,
    output_root: str | Path,
    top_k: int,
    logger: logging.Logger,
    copy_failure_images: bool = True,
) -> Dict[str, Any]:
    """Generate failure-case tables and optionally copy top-K failure images."""
    if predictions_table.empty:
        return {
            "status": "skipped",
            "reason": "Predictions table is empty",
            "paths": {},
        }

    output_dir = Path(output_root) / "failure_cases"
    output_dir.mkdir(parents=True, exist_ok=True)

    table = predictions_table.copy()

    if "predicted_label_index" not in table.columns:
        if "predicted_label" in table.columns:
            table["predicted_label_index"] = table["predicted_label"].astype(str).str.upper().map({"REAL": 0, "FAKE": 1}).fillna(0).astype(int)
        else:
            raise KeyError("predictions_table must include predicted_label_index or predicted_label")

    if "correct" not in table.columns:
        table["correct"] = table["true_label"].astype(int) == table["predicted_label_index"].astype(int)

    table["predicted_probability"] = table["predicted_probability"].astype(float)
    table["wrong_confidence"] = table.apply(
        lambda row: row["predicted_probability"] if int(row["predicted_label_index"]) == 1 else (1.0 - row["predicted_probability"]),
        axis=1,
    )
    table["uncertainty_distance_to_half"] = (table["predicted_probability"] - 0.5).abs()

    false_positives = table[(table["true_label"].astype(int) == 0) & (table["predicted_label_index"].astype(int) == 1)].copy()
    false_negatives = table[(table["true_label"].astype(int) == 1) & (table["predicted_label_index"].astype(int) == 0)].copy()
    wrong_predictions = table[~table["correct"].astype(bool)].copy()

    top_fp = false_positives.sort_values(by="wrong_confidence", ascending=False).head(int(top_k)).copy()
    top_fn = false_negatives.sort_values(by="wrong_confidence", ascending=False).head(int(top_k)).copy()
    hardest = wrong_predictions.sort_values(by="wrong_confidence", ascending=False).head(int(top_k)).copy()
    most_uncertain = table.sort_values(by="uncertainty_distance_to_half", ascending=True).head(int(top_k)).copy()

    # Keep core metadata columns when present.
    preferred_columns = [
        "filepath",
        "split",
        "dataset",
        "source_dataset",
        "predicted_probability",
        "predicted_label",
        "predicted_label_index",
        "true_label",
        "correct",
        "wrong_confidence",
        "uncertainty_distance_to_half",
        "blur_score",
        "brightness",
        "brightness_score",
    ]

    def _select_columns(df: pd.DataFrame) -> pd.DataFrame:
        keep = [col for col in preferred_columns if col in df.columns]
        if not keep:
            return df
        return df[keep]

    top_fp = _select_columns(top_fp)
    top_fn = _select_columns(top_fn)
    hardest = _select_columns(hardest)
    most_uncertain = _select_columns(most_uncertain)

    fp_path = output_dir / "top_false_positives.csv"
    fn_path = output_dir / "top_false_negatives.csv"
    hardest_path = output_dir / "hardest_samples.csv"
    uncertain_path = output_dir / "most_uncertain_samples.csv"

    save_dataframe_csv(top_fp, fp_path)
    save_dataframe_csv(top_fn, fn_path)
    save_dataframe_csv(hardest, hardest_path)
    save_dataframe_csv(most_uncertain, uncertain_path)

    copied_count = 0
    if copy_failure_images:
        copied_count += _copy_failure_images(top_fp, output_dir / "top_false_positives", logger)
        copied_count += _copy_failure_images(top_fn, output_dir / "top_false_negatives", logger)

    summary = {
        "num_false_positives": int(false_positives.shape[0]),
        "num_false_negatives": int(false_negatives.shape[0]),
        "num_wrong_predictions": int(wrong_predictions.shape[0]),
        "num_copied_failure_images": int(copied_count),
        "top_false_positives_csv": str(fp_path.as_posix()),
        "top_false_negatives_csv": str(fn_path.as_posix()),
        "hardest_samples_csv": str(hardest_path.as_posix()),
        "most_uncertain_samples_csv": str(uncertain_path.as_posix()),
    }

    summary_path = output_dir / "failure_analysis_summary.json"
    save_dict_json(summary, summary_path)

    return {
        "status": "ok",
        "summary": summary,
        "paths": {
            "summary_json": str(summary_path.as_posix()),
            "top_fp_csv": str(fp_path.as_posix()),
            "top_fn_csv": str(fn_path.as_posix()),
            "hardest_csv": str(hardest_path.as_posix()),
            "uncertain_csv": str(uncertain_path.as_posix()),
        },
        "tables": {
            "top_false_positives": top_fp,
            "top_false_negatives": top_fn,
            "hardest_samples": hardest,
            "most_uncertain_samples": most_uncertain,
        },
    }


def _copy_failure_images(table: pd.DataFrame, destination_dir: Path, logger: logging.Logger) -> int:
    """Copy failure images from table filepath column into destination folder."""
    if table.empty or "filepath" not in table.columns:
        return 0

    destination_dir.mkdir(parents=True, exist_ok=True)
    copied = 0

    for idx, row in table.iterrows():
        source = Path(str(row["filepath"]))
        if not source.exists() or not source.is_file():
            logger.warning("Failure image source missing: %s", source)
            continue

        filename = f"{idx:04d}_{sanitize_filename(source.name)}"
        destination = destination_dir / filename
        _, error = copy_file_safe(source, destination, overwrite=True)
        if error is None:
            copied += 1
        else:
            logger.warning("Failed to copy failure image %s: %s", source, error)

    return copied
