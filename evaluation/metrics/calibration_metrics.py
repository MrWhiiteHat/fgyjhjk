"""Calibration metrics and temperature scaling utilities."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import torch


@dataclass
class TemperatureScaler:
    """Single-parameter temperature scaling calibrator for logits."""

    temperature: float = 1.0

    def fit(
        self,
        logits: Sequence[float],
        labels: Sequence[int],
        max_iter: int = 300,
        lr: float = 0.01,
        logger: Optional[logging.Logger] = None,
    ) -> float:
        """Fit temperature on validation logits and labels only."""
        logits_np = np.asarray(logits, dtype=np.float32).reshape(-1)
        labels_np = np.asarray(labels, dtype=np.float32).reshape(-1)

        if logits_np.size == 0:
            raise ValueError("Temperature scaling fit requires non-empty logits")

        logits_tensor = torch.tensor(logits_np, dtype=torch.float32)
        labels_tensor = torch.tensor(labels_np, dtype=torch.float32)

        log_temperature = torch.nn.Parameter(torch.zeros(1, dtype=torch.float32))
        optimizer = torch.optim.Adam([log_temperature], lr=float(lr))
        criterion = torch.nn.BCEWithLogitsLoss()

        for _ in range(int(max_iter)):
            optimizer.zero_grad(set_to_none=True)
            temperature = torch.exp(log_temperature).clamp(min=1e-3, max=100.0)
            scaled_logits = logits_tensor / temperature
            loss = criterion(scaled_logits, labels_tensor)
            loss.backward()
            optimizer.step()

        fitted_temperature = float(torch.exp(log_temperature.detach()).item())
        self.temperature = max(fitted_temperature, 1e-3)

        if logger is not None:
            logger.info("Fitted temperature scaling parameter: %.6f", self.temperature)

        return self.temperature

    def transform_logits(self, logits: Sequence[float]) -> np.ndarray:
        """Scale logits with fitted temperature."""
        logits_np = np.asarray(logits, dtype=np.float64)
        return logits_np / float(max(self.temperature, 1e-6))

    def transform_probabilities(self, logits: Sequence[float]) -> np.ndarray:
        """Convert scaled logits to calibrated probabilities."""
        scaled_logits = self.transform_logits(logits)
        clipped = np.clip(scaled_logits, -60.0, 60.0)
        return 1.0 / (1.0 + np.exp(-clipped))


def _compute_bin_stats(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    num_bins: int,
) -> pd.DataFrame:
    """Compute bin-level calibration statistics for reliability analysis."""
    bins = np.linspace(0.0, 1.0, int(num_bins) + 1)
    rows = []

    for idx in range(len(bins) - 1):
        left = bins[idx]
        right = bins[idx + 1]
        if idx == len(bins) - 2:
            mask = (y_prob >= left) & (y_prob <= right)
        else:
            mask = (y_prob >= left) & (y_prob < right)

        count = int(mask.sum())
        if count == 0:
            bin_confidence = 0.0
            bin_accuracy = 0.0
        else:
            bin_confidence = float(np.mean(y_prob[mask]))
            bin_accuracy = float(np.mean(y_true[mask]))

        rows.append(
            {
                "bin_index": idx,
                "bin_left": float(left),
                "bin_right": float(right),
                "bin_count": int(count),
                "bin_confidence": float(bin_confidence),
                "bin_accuracy": float(bin_accuracy),
                "bin_gap": float(abs(bin_accuracy - bin_confidence)),
            }
        )

    return pd.DataFrame(rows)


def compute_calibration_metrics(
    y_true: Sequence[int],
    y_prob: Sequence[float],
    num_bins: int = 15,
) -> Dict[str, Any]:
    """Compute ECE, MCE, Brier score, reliability bins, and histogram counts."""
    y_true_np = np.asarray(y_true, dtype=np.float64).reshape(-1)
    y_prob_np = np.asarray(y_prob, dtype=np.float64).reshape(-1)

    if y_true_np.size == 0:
        return {
            "num_samples": 0,
            "ece": float("nan"),
            "mce": float("nan"),
            "brier_score": float("nan"),
            "bin_table": pd.DataFrame(),
            "hist_counts": [],
            "hist_edges": [],
            "platt_scaling_note": "Platt scaling is not implemented in this module.",
        }

    bin_table = _compute_bin_stats(y_true_np, y_prob_np, num_bins=num_bins)
    total_count = float(max(y_true_np.size, 1))

    ece = float((bin_table["bin_count"] / total_count * bin_table["bin_gap"]).sum())
    mce = float(bin_table["bin_gap"].max()) if not bin_table.empty else 0.0
    brier_score = float(np.mean((y_prob_np - y_true_np) ** 2))

    hist_counts, hist_edges = np.histogram(y_prob_np, bins=num_bins, range=(0.0, 1.0))

    return {
        "num_samples": int(y_true_np.size),
        "ece": float(ece),
        "mce": float(mce),
        "brier_score": float(brier_score),
        "bin_table": bin_table,
        "hist_counts": hist_counts.tolist(),
        "hist_edges": hist_edges.tolist(),
        "platt_scaling_note": "Platt scaling is not implemented in this module.",
    }


def compare_raw_vs_calibrated(
    y_true: Sequence[int],
    raw_probabilities: Sequence[float],
    calibrated_probabilities: Sequence[float],
    num_bins: int = 15,
) -> Dict[str, Any]:
    """Compute side-by-side calibration metrics for raw and calibrated probabilities."""
    raw_metrics = compute_calibration_metrics(y_true=y_true, y_prob=raw_probabilities, num_bins=num_bins)
    calibrated_metrics = compute_calibration_metrics(y_true=y_true, y_prob=calibrated_probabilities, num_bins=num_bins)

    return {
        "raw": {
            "ece": raw_metrics["ece"],
            "mce": raw_metrics["mce"],
            "brier_score": raw_metrics["brier_score"],
        },
        "calibrated": {
            "ece": calibrated_metrics["ece"],
            "mce": calibrated_metrics["mce"],
            "brier_score": calibrated_metrics["brier_score"],
        },
        "raw_bin_table": raw_metrics["bin_table"],
        "calibrated_bin_table": calibrated_metrics["bin_table"],
    }


def calibrate_probabilities_with_temperature(
    val_logits: Sequence[float],
    val_labels: Sequence[int],
    target_logits: Sequence[float],
    logger: Optional[logging.Logger] = None,
) -> Tuple[np.ndarray, Dict[str, float]]:
    """Fit temperature on validation split and apply to target logits."""
    scaler = TemperatureScaler(temperature=1.0)
    fitted_temperature = scaler.fit(logits=val_logits, labels=val_labels, logger=logger)
    calibrated_prob = scaler.transform_probabilities(target_logits)

    details = {
        "temperature": float(fitted_temperature),
    }
    return calibrated_prob, details
