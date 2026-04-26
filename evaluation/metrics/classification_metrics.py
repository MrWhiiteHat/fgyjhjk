"""Binary classification metric computation for real-vs-fake evaluation."""

from __future__ import annotations

from typing import Any, Dict, Sequence, Tuple

import numpy as np
import pandas as pd

from evaluation.utils.helpers import safe_div


def compute_confusion_counts(y_true: Sequence[int], y_pred: Sequence[int]) -> Dict[str, int]:
    """Compute TP/TN/FP/FN counts for binary predictions."""
    y_true_np = np.asarray(y_true, dtype=np.int64)
    y_pred_np = np.asarray(y_pred, dtype=np.int64)

    tp = int(np.sum((y_true_np == 1) & (y_pred_np == 1)))
    tn = int(np.sum((y_true_np == 0) & (y_pred_np == 0)))
    fp = int(np.sum((y_true_np == 0) & (y_pred_np == 1)))
    fn = int(np.sum((y_true_np == 1) & (y_pred_np == 0)))

    return {
        "tp": int(tp),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
    }


def _compute_roc_curve(y_true: np.ndarray, y_prob: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Compute ROC curve points for binary labels."""
    order = np.argsort(-y_prob)
    y_true_sorted = y_true[order]

    tps = np.cumsum(y_true_sorted == 1)
    fps = np.cumsum(y_true_sorted == 0)

    positives = max(int(np.sum(y_true == 1)), 1)
    negatives = max(int(np.sum(y_true == 0)), 1)

    tpr = tps / positives
    fpr = fps / negatives

    tpr = np.concatenate(([0.0], tpr, [1.0]))
    fpr = np.concatenate(([0.0], fpr, [1.0]))
    return fpr, tpr


def _compute_pr_curve(y_true: np.ndarray, y_prob: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Compute precision-recall curve points for binary labels."""
    order = np.argsort(-y_prob)
    y_true_sorted = y_true[order]

    tps = np.cumsum(y_true_sorted == 1)
    fps = np.cumsum(y_true_sorted == 0)

    precision = tps / np.maximum(tps + fps, 1)
    positives = max(int(np.sum(y_true == 1)), 1)
    recall = tps / positives

    precision = np.concatenate(([1.0], precision, [0.0]))
    recall = np.concatenate(([0.0], recall, [1.0]))
    return recall, precision


def _compute_auc(x: np.ndarray, y: np.ndarray) -> float:
    """Compute area under curve with trapezoidal integration."""
    return float(np.trapezoid(y, x))


def compute_classification_metrics(
    y_true: Sequence[int],
    y_prob: Sequence[float],
    threshold: float,
) -> Dict[str, Any]:
    """Compute threshold-dependent and threshold-independent binary metrics."""
    y_true_np = np.asarray(y_true, dtype=np.int64)
    y_prob_np = np.asarray(y_prob, dtype=np.float64)

    if y_true_np.size == 0:
        return {
            "num_samples": 0,
            "threshold": float(threshold),
            "accuracy": float("nan"),
            "precision": float("nan"),
            "recall": float("nan"),
            "f1": float("nan"),
            "balanced_accuracy": float("nan"),
            "specificity": float("nan"),
            "sensitivity": float("nan"),
            "roc_auc": float("nan"),
            "pr_auc": float("nan"),
            "false_positive_rate": float("nan"),
            "false_negative_rate": float("nan"),
            "matthews_correlation_coefficient": float("nan"),
            "confusion_matrix": np.zeros((2, 2), dtype=np.int64),
            "tp": 0,
            "tn": 0,
            "fp": 0,
            "fn": 0,
        }

    y_pred_np = (y_prob_np >= float(threshold)).astype(np.int64)

    counts = compute_confusion_counts(y_true_np, y_pred_np)
    tp = counts["tp"]
    tn = counts["tn"]
    fp = counts["fp"]
    fn = counts["fn"]
    cm = np.asarray([[tn, fp], [fn, tp]], dtype=np.int64)

    sensitivity = safe_div(tp, tp + fn, default=0.0)
    specificity = safe_div(tn, tn + fp, default=0.0)
    fpr = safe_div(fp, fp + tn, default=0.0)
    fnr = safe_div(fn, fn + tp, default=0.0)

    accuracy = safe_div(tp + tn, tp + tn + fp + fn, default=0.0)
    precision = safe_div(tp, tp + fp, default=0.0)
    recall = sensitivity
    f1 = safe_div(2.0 * precision * recall, precision + recall, default=0.0)
    balanced_accuracy = (sensitivity + specificity) / 2.0

    unique_classes = np.unique(y_true_np)
    if unique_classes.size >= 2:
        roc_x, roc_y = _compute_roc_curve(y_true_np, y_prob_np)
        pr_x, pr_y = _compute_pr_curve(y_true_np, y_prob_np)
        roc_auc = _compute_auc(roc_x, roc_y)
        pr_auc = _compute_auc(pr_x, pr_y)
    else:
        roc_auc = float("nan")
        pr_auc = float("nan")

    mcc_denom = np.sqrt(float((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn)))
    if mcc_denom <= 0:
        mcc_value = 0.0
    else:
        mcc_value = float(((tp * tn) - (fp * fn)) / mcc_denom)

    metrics = {
        "num_samples": int(y_true_np.size),
        "threshold": float(threshold),
        "accuracy": float(accuracy),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "balanced_accuracy": float(balanced_accuracy),
        "specificity": float(specificity),
        "sensitivity": float(sensitivity),
        "roc_auc": float(roc_auc),
        "pr_auc": float(pr_auc),
        "false_positive_rate": float(fpr),
        "false_negative_rate": float(fnr),
        "matthews_correlation_coefficient": float(mcc_value),
        "confusion_matrix": cm.astype(np.int64),
        "tp": int(tp),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
    }

    return metrics


def metrics_to_table(metrics: Dict[str, Any]) -> pd.DataFrame:
    """Convert metrics dictionary to saveable table format."""
    excluded = {"confusion_matrix"}
    rows = []
    for key, value in metrics.items():
        if key in excluded:
            continue
        rows.append({"metric": key, "value": value})
    return pd.DataFrame(rows)


def build_epoch_metrics(
    true_labels: Sequence[int],
    probabilities: Sequence[float],
    threshold: float,
) -> Tuple[Dict[str, Any], pd.DataFrame]:
    """Compute metrics and table from full-epoch prediction arrays."""
    metrics = compute_classification_metrics(true_labels, probabilities, threshold)
    table = metrics_to_table(metrics)
    return metrics, table
