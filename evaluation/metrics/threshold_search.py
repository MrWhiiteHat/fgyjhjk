"""Threshold sweep utilities for validation-only decision threshold tuning."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Sequence

import numpy as np
import pandas as pd

from evaluation.utils.io import save_dataframe_csv
from evaluation.utils.visualization import plot_threshold_sweep_curve


def search_best_threshold(
    y_true: Sequence[int],
    y_prob: Sequence[float],
    metric: str,
    threshold_min: float,
    threshold_max: float,
    threshold_step: float,
    recall_constraint: float = 0.90,
    output_csv_path: str | Path | None = None,
    output_plot_path: str | Path | None = None,
) -> Dict[str, Any]:
    """Sweep thresholds and choose best value using configured optimization target."""
    y_true_np = np.asarray(y_true, dtype=np.int64)
    y_prob_np = np.asarray(y_prob, dtype=np.float64)

    if y_true_np.size == 0:
        raise ValueError("Threshold search requires non-empty validation labels")

    if threshold_step <= 0:
        raise ValueError("threshold_step must be > 0")

    if threshold_min >= threshold_max:
        raise ValueError("threshold_min must be < threshold_max")

    target = str(metric).strip().lower()
    thresholds = np.arange(float(threshold_min), float(threshold_max) + 1e-12, float(threshold_step))

    rows = []
    best_threshold = float(thresholds[0])
    best_score = -np.inf
    best_row: Dict[str, Any] = {}

    for threshold in thresholds:
        pred = (y_prob_np >= threshold).astype(np.int64)

        tp = int(((pred == 1) & (y_true_np == 1)).sum())
        tn = int(((pred == 0) & (y_true_np == 0)).sum())
        fp = int(((pred == 1) & (y_true_np == 0)).sum())
        fn = int(((pred == 0) & (y_true_np == 1)).sum())

        precision = float(tp / max(tp + fp, 1))
        recall = float(tp / max(tp + fn, 1))
        f1 = float((2.0 * precision * recall) / max(precision + recall, 1e-12))

        tpr = float(tp / max(tp + fn, 1))
        tnr = float(tn / max(tn + fp, 1))
        balanced_acc = float((tpr + tnr) / 2.0)

        youdens_j = float(tpr + tnr - 1.0)

        if target == "f1":
            score = f1
        elif target == "balanced_accuracy":
            score = balanced_acc
        elif target in {"youdens_j", "youden", "youden_j"}:
            score = youdens_j
        elif target in {"precision_at_recall", "precision_at_recall_constraint"}:
            score = precision if recall >= float(recall_constraint) else -np.inf
        else:
            raise ValueError(
                "Unsupported threshold_search_metric. Supported values: "
                "f1, balanced_accuracy, youdens_j, precision_at_recall"
            )

        row = {
            "threshold": float(threshold),
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "balanced_accuracy": balanced_acc,
            "youdens_j": youdens_j,
            "score": float(score),
            "target_metric": target,
        }
        rows.append(row)

        if score > best_score:
            best_score = float(score)
            best_threshold = float(threshold)
            best_row = row

    sweep_table = pd.DataFrame(rows)

    if output_csv_path is not None:
        save_dataframe_csv(sweep_table, output_csv_path)

    if output_plot_path is not None:
        plot_threshold_sweep_curve(
            sweep_table=sweep_table,
            output_path=output_plot_path,
            metric_column="score",
            title=f"Threshold Sweep ({target})",
        )

    if np.isneginf(best_score):
        rationale = (
            "No threshold satisfied the precision-at-recall constraint on validation split. "
            "Falling back to threshold with highest unconstrained precision among searched thresholds."
        )
        fallback_idx = int(sweep_table["precision"].idxmax())
        fallback_row = sweep_table.loc[fallback_idx]
        best_threshold = float(fallback_row["threshold"])
        best_score = float(fallback_row["precision"])
        best_row = dict(fallback_row)
    else:
        rationale = f"Selected threshold maximizing '{target}' on validation split."

    return {
        "best_threshold": float(best_threshold),
        "best_score": float(best_score),
        "metric": target,
        "rationale": rationale,
        "best_row": best_row,
        "sweep_table": sweep_table,
    }
