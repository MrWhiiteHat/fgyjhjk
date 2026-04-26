"""Visualization utilities for metrics, curves, and summary reports."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.metrics import PrecisionRecallDisplay, RocCurveDisplay

from .helpers import save_json


def plot_training_curves(history_df: pd.DataFrame, plots_dir: Path) -> Dict[str, Path]:
    """Generate train-vs-val loss/accuracy/F1 curves from history dataframe."""
    plots_dir.mkdir(parents=True, exist_ok=True)
    outputs: Dict[str, Path] = {}

    if history_df.empty:
        return outputs

    # Loss curve
    loss_path = plots_dir / "loss_curve.png"
    plt.figure(figsize=(9, 5))
    plt.plot(history_df["epoch"], history_df.get("train_loss", np.nan), label="Train Loss")
    plt.plot(history_df["epoch"], history_df.get("val_loss", np.nan), label="Val Loss")
    plt.xlabel("Epoch")
    plt.ylabel("Loss")
    plt.title("Train vs Validation Loss")
    plt.legend()
    plt.grid(alpha=0.2)
    plt.tight_layout()
    plt.savefig(loss_path, dpi=150)
    plt.close()
    outputs["loss_curve"] = loss_path

    # Accuracy curve
    acc_path = plots_dir / "accuracy_curve.png"
    plt.figure(figsize=(9, 5))
    plt.plot(history_df["epoch"], history_df.get("train_accuracy", np.nan), label="Train Accuracy")
    plt.plot(history_df["epoch"], history_df.get("val_accuracy", np.nan), label="Val Accuracy")
    plt.xlabel("Epoch")
    plt.ylabel("Accuracy")
    plt.title("Train vs Validation Accuracy")
    plt.legend()
    plt.grid(alpha=0.2)
    plt.tight_layout()
    plt.savefig(acc_path, dpi=150)
    plt.close()
    outputs["accuracy_curve"] = acc_path

    # F1 curve
    f1_path = plots_dir / "f1_curve.png"
    plt.figure(figsize=(9, 5))
    plt.plot(history_df["epoch"], history_df.get("train_f1", np.nan), label="Train F1")
    plt.plot(history_df["epoch"], history_df.get("val_f1", np.nan), label="Val F1")
    plt.xlabel("Epoch")
    plt.ylabel("F1")
    plt.title("Train vs Validation F1")
    plt.legend()
    plt.grid(alpha=0.2)
    plt.tight_layout()
    plt.savefig(f1_path, dpi=150)
    plt.close()
    outputs["f1_curve"] = f1_path

    return outputs


def plot_roc_curve(y_true: Sequence[int], y_prob: Sequence[float], output_path: Path, title: str) -> Path:
    """Create ROC curve image from labels and probabilities."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=(6, 6))
    RocCurveDisplay.from_predictions(y_true, y_prob)
    plt.title(title)
    plt.grid(alpha=0.2)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    return output_path


def plot_pr_curve(y_true: Sequence[int], y_prob: Sequence[float], output_path: Path, title: str) -> Path:
    """Create precision-recall curve image from labels and probabilities."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=(6, 6))
    PrecisionRecallDisplay.from_predictions(y_true, y_prob)
    plt.title(title)
    plt.grid(alpha=0.2)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    return output_path


def plot_confusion_matrix(confusion: np.ndarray, output_path: Path, title: str) -> Path:
    """Render confusion matrix heatmap and save to disk."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    labels = ["REAL", "FAKE"]
    plt.figure(figsize=(6, 5))
    sns.heatmap(
        confusion,
        annot=True,
        fmt="d",
        cmap="Blues",
        xticklabels=labels,
        yticklabels=labels,
        cbar=False,
    )
    plt.xlabel("Predicted")
    plt.ylabel("True")
    plt.title(title)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    return output_path


def generate_experiment_report(report_path: Path, payload: Dict) -> Path:
    """Save final experiment report as JSON and TXT sidecar."""
    report_path.parent.mkdir(parents=True, exist_ok=True)

    save_json(payload, report_path)

    txt_path = report_path.with_suffix(".txt")
    with txt_path.open("w", encoding="utf-8") as handle:
        handle.write("Experiment Report\n")
        handle.write("=================\n")
        for key, value in payload.items():
            handle.write(f"{key}: {value}\n")

    return report_path
