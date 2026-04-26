"""Metric computation utilities for binary classification."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def sigmoid_numpy(values: np.ndarray) -> np.ndarray:
    """Compute sigmoid in a numerically stable way for numpy arrays."""
    clipped = np.clip(values, -60.0, 60.0)
    return 1.0 / (1.0 + np.exp(-clipped))


def compute_binary_metrics(y_true: Sequence[int], y_prob: Sequence[float], threshold: float) -> Dict:
    """Compute binary metrics from true labels and probability predictions."""
    y_true_np = np.asarray(y_true, dtype=np.int64)
    y_prob_np = np.asarray(y_prob, dtype=np.float64)

    if y_true_np.size == 0:
        empty_cm = np.zeros((2, 2), dtype=np.int64)
        return {
            "accuracy": float("nan"),
            "precision": float("nan"),
            "recall": float("nan"),
            "f1": float("nan"),
            "roc_auc": float("nan"),
            "pr_auc": float("nan"),
            "balanced_accuracy": float("nan"),
            "confusion_matrix": empty_cm,
        }

    y_pred_np = (y_prob_np >= float(threshold)).astype(np.int64)

    metrics = {
        "accuracy": float(accuracy_score(y_true_np, y_pred_np)),
        "precision": float(precision_score(y_true_np, y_pred_np, zero_division=0)),
        "recall": float(recall_score(y_true_np, y_pred_np, zero_division=0)),
        "f1": float(f1_score(y_true_np, y_pred_np, zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true_np, y_pred_np)),
        "confusion_matrix": confusion_matrix(y_true_np, y_pred_np, labels=[0, 1]),
    }

    unique_classes = np.unique(y_true_np)
    if unique_classes.size < 2:
        metrics["roc_auc"] = float("nan")
        metrics["pr_auc"] = float("nan")
    else:
        metrics["roc_auc"] = float(roc_auc_score(y_true_np, y_prob_np))
        metrics["pr_auc"] = float(average_precision_score(y_true_np, y_prob_np))

    return metrics


@dataclass
class EpochMetricTracker:
    """Accumulate logits/probabilities/labels over full epoch for stable metrics."""

    split_name: str
    losses: List[float] = field(default_factory=list)
    logits: List[float] = field(default_factory=list)
    labels: List[int] = field(default_factory=list)
    probabilities: List[float] = field(default_factory=list)
    filepaths: List[str] = field(default_factory=list)

    def update(self, loss: float, logits: np.ndarray, labels: np.ndarray, filepaths: Sequence[str]) -> None:
        """Add batch outputs to epoch-level storage."""
        logits_flat = logits.reshape(-1).astype(np.float64)
        labels_flat = labels.reshape(-1).astype(np.int64)
        probs_flat = sigmoid_numpy(logits_flat)

        self.losses.append(float(loss))
        self.logits.extend([float(x) for x in logits_flat.tolist()])
        self.labels.extend([int(x) for x in labels_flat.tolist()])
        self.probabilities.extend([float(x) for x in probs_flat.tolist()])
        self.filepaths.extend([str(p) for p in filepaths])

    def compute(self, threshold: float) -> Tuple[Dict, Dict]:
        """Compute aggregate metrics and return metrics plus raw arrays."""
        metrics = compute_binary_metrics(self.labels, self.probabilities, threshold=threshold)
        metrics["loss"] = float(np.mean(self.losses)) if self.losses else float("nan")

        raw_outputs = {
            "labels": np.asarray(self.labels, dtype=np.int64),
            "logits": np.asarray(self.logits, dtype=np.float64),
            "probabilities": np.asarray(self.probabilities, dtype=np.float64),
            "predictions": (np.asarray(self.probabilities, dtype=np.float64) >= float(threshold)).astype(np.int64),
            "filepaths": list(self.filepaths),
        }
        return metrics, raw_outputs
