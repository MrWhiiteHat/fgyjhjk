"""Visualization utilities for evaluation metrics and inference diagnostics."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from evaluation.utils.helpers import now_timestamp


def _prepare_output_path(output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _title_with_timestamp(title: str) -> str:
    return f"{title} | {now_timestamp()}"


def _roc_curve_points(y_true: np.ndarray, y_prob: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Compute ROC curve points without external metric dependencies."""
    order = np.argsort(-y_prob)
    y_sorted = y_true[order]

    tps = np.cumsum(y_sorted == 1)
    fps = np.cumsum(y_sorted == 0)

    positives = max(int(np.sum(y_true == 1)), 1)
    negatives = max(int(np.sum(y_true == 0)), 1)

    tpr = tps / positives
    fpr = fps / negatives

    tpr = np.concatenate(([0.0], tpr, [1.0]))
    fpr = np.concatenate(([0.0], fpr, [1.0]))
    return fpr, tpr


def _pr_curve_points(y_true: np.ndarray, y_prob: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Compute precision-recall points without sklearn."""
    order = np.argsort(-y_prob)
    y_sorted = y_true[order]

    tps = np.cumsum(y_sorted == 1)
    fps = np.cumsum(y_sorted == 0)

    precision = tps / np.maximum(tps + fps, 1)
    positives = max(int(np.sum(y_true == 1)), 1)
    recall = tps / positives

    precision = np.concatenate(([1.0], precision, [0.0]))
    recall = np.concatenate(([0.0], recall, [1.0]))
    return recall, precision


def plot_roc_curve(
    y_true: Sequence[int],
    y_prob: Sequence[float],
    output_path: str | Path,
    title: str = "ROC Curve",
) -> Path:
    """Plot and save ROC curve with timestamped title."""
    output = _prepare_output_path(output_path)
    y_true_np = np.asarray(y_true, dtype=np.int64)
    y_prob_np = np.asarray(y_prob, dtype=np.float64)

    plt.figure(figsize=(7, 6))
    if np.unique(y_true_np).size >= 2:
        fpr, tpr = _roc_curve_points(y_true_np, y_prob_np)
        auc_value = float(np.trapezoid(tpr, fpr))
        plt.plot(fpr, tpr, label=f"ROC AUC = {auc_value:.4f}")
        plt.plot([0, 1], [0, 1], linestyle="--", color="gray", label="Chance")
        plt.legend()
        plt.ylabel("True Positive Rate")
        plt.xlabel("False Positive Rate")
    else:
        plt.text(0.5, 0.5, "ROC unavailable: only one class present", ha="center", va="center")
        plt.xlim(0.0, 1.0)
        plt.ylim(0.0, 1.0)
        plt.xlabel("False Positive Rate")
        plt.ylabel("True Positive Rate")
    plt.title(_title_with_timestamp(title))
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(output, dpi=180)
    plt.close()
    return output


def plot_pr_curve(
    y_true: Sequence[int],
    y_prob: Sequence[float],
    output_path: str | Path,
    title: str = "Precision-Recall Curve",
) -> Path:
    """Plot and save precision-recall curve with timestamped title."""
    output = _prepare_output_path(output_path)
    y_true_np = np.asarray(y_true, dtype=np.int64)
    y_prob_np = np.asarray(y_prob, dtype=np.float64)

    plt.figure(figsize=(7, 6))
    if np.unique(y_true_np).size >= 2:
        recall, precision = _pr_curve_points(y_true_np, y_prob_np)
        auc_value = float(np.trapezoid(precision, recall))
        plt.plot(recall, precision, label=f"PR AUC = {auc_value:.4f}")
        plt.legend()
        plt.xlabel("Recall")
        plt.ylabel("Precision")
    else:
        plt.text(0.5, 0.5, "PR unavailable: only one class present", ha="center", va="center")
        plt.xlim(0.0, 1.0)
        plt.ylim(0.0, 1.0)
        plt.xlabel("Recall")
        plt.ylabel("Precision")
    plt.title(_title_with_timestamp(title))
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(output, dpi=180)
    plt.close()
    return output


def plot_confusion_matrix_heatmap(
    matrix: np.ndarray,
    output_path: str | Path,
    class_names: Sequence[str],
    title: str = "Confusion Matrix",
    normalize: bool = False,
) -> Path:
    """Plot and save raw or row-normalized confusion matrix."""
    output = _prepare_output_path(output_path)
    matrix_np = np.asarray(matrix, dtype=np.float64)

    display_values = matrix_np.copy()
    fmt = ".2f" if normalize else "d"
    if normalize:
        row_sum = display_values.sum(axis=1, keepdims=True)
        row_sum[row_sum == 0] = 1.0
        display_values = display_values / row_sum
    else:
        display_values = display_values.astype(np.int64)

    plt.figure(figsize=(6.5, 5.5))
    sns.heatmap(
        display_values,
        annot=True,
        fmt=fmt,
        cmap="Blues",
        cbar=False,
        xticklabels=list(class_names),
        yticklabels=list(class_names),
    )
    plt.xlabel("Predicted Label")
    plt.ylabel("True Label")
    subtitle = "Normalized" if normalize else "Raw"
    plt.title(_title_with_timestamp(f"{title} ({subtitle})"))
    plt.tight_layout()
    plt.savefig(output, dpi=180)
    plt.close()
    return output


def plot_reliability_diagram(
    bin_table: pd.DataFrame,
    output_path: str | Path,
    title: str = "Reliability Diagram",
) -> Path:
    """Plot reliability diagram from calibration bin statistics."""
    output = _prepare_output_path(output_path)
    table = bin_table.copy()

    plt.figure(figsize=(7, 6))
    plt.plot([0, 1], [0, 1], linestyle="--", color="gray", label="Perfect Calibration")

    if not table.empty and {"bin_confidence", "bin_accuracy"}.issubset(set(table.columns)):
        plt.plot(table["bin_confidence"], table["bin_accuracy"], marker="o", label="Model")
    else:
        plt.text(0.5, 0.5, "No calibration bins available", ha="center", va="center")

    plt.xlabel("Mean Predicted Probability")
    plt.ylabel("Observed Positive Rate")
    plt.title(_title_with_timestamp(title))
    plt.xlim(0.0, 1.0)
    plt.ylim(0.0, 1.0)
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output, dpi=180)
    plt.close()
    return output


def plot_probability_histogram(
    probabilities: Sequence[float],
    output_path: str | Path,
    title: str = "Probability Distribution",
    bins: int = 20,
) -> Path:
    """Plot histogram of probabilities for model confidence distribution."""
    output = _prepare_output_path(output_path)
    probs = np.asarray(probabilities, dtype=np.float64)

    plt.figure(figsize=(7, 5))
    if probs.size > 0:
        plt.hist(probs, bins=int(bins), range=(0.0, 1.0), color="#1f77b4", alpha=0.85)
    else:
        plt.text(0.5, 0.5, "No probabilities available", ha="center", va="center")
    plt.xlabel("Predicted Probability (FAKE class)")
    plt.ylabel("Count")
    plt.title(_title_with_timestamp(title))
    plt.grid(axis="y", alpha=0.25)
    plt.tight_layout()
    plt.savefig(output, dpi=180)
    plt.close()
    return output


def plot_threshold_sweep_curve(
    sweep_table: pd.DataFrame,
    output_path: str | Path,
    metric_column: str,
    title: str = "Threshold Sweep",
) -> Path:
    """Plot threshold vs metric curve from sweep dataframe."""
    output = _prepare_output_path(output_path)

    plt.figure(figsize=(8, 5))
    if not sweep_table.empty and {"threshold", metric_column}.issubset(set(sweep_table.columns)):
        plt.plot(sweep_table["threshold"], sweep_table[metric_column], marker="o", markersize=3)
        best_idx = int(sweep_table[metric_column].idxmax())
        best_row = sweep_table.loc[best_idx]
        plt.scatter([best_row["threshold"]], [best_row[metric_column]], color="red", s=50, label="Best")
        plt.legend()
    else:
        plt.text(0.5, 0.5, "No sweep data available", ha="center", va="center")

    plt.xlabel("Threshold")
    plt.ylabel(metric_column)
    plt.title(_title_with_timestamp(title))
    plt.grid(alpha=0.25)
    plt.tight_layout()
    plt.savefig(output, dpi=180)
    plt.close()
    return output


def plot_inference_confidence_histogram(
    probabilities: Sequence[float],
    predicted_labels: Optional[Sequence[int]],
    output_path: str | Path,
    title: str = "Inference Confidence Histogram",
    bins: int = 20,
) -> Path:
    """Plot confidence histogram optionally separated by predicted class."""
    output = _prepare_output_path(output_path)
    probs = np.asarray(probabilities, dtype=np.float64)

    plt.figure(figsize=(8, 5))
    if probs.size == 0:
        plt.text(0.5, 0.5, "No confidence values available", ha="center", va="center")
    elif predicted_labels is None:
        plt.hist(probs, bins=int(bins), range=(0.0, 1.0), alpha=0.85, color="#2ca02c")
    else:
        labels = np.asarray(predicted_labels, dtype=np.int64)
        real_probs = probs[labels == 0]
        fake_probs = probs[labels == 1]
        if real_probs.size > 0:
            plt.hist(real_probs, bins=int(bins), range=(0.0, 1.0), alpha=0.65, label="Pred REAL")
        if fake_probs.size > 0:
            plt.hist(fake_probs, bins=int(bins), range=(0.0, 1.0), alpha=0.65, label="Pred FAKE")
        plt.legend()

    plt.xlabel("Predicted Probability (FAKE class)")
    plt.ylabel("Count")
    plt.title(_title_with_timestamp(title))
    plt.grid(axis="y", alpha=0.25)
    plt.tight_layout()
    plt.savefig(output, dpi=180)
    plt.close()
    return output
