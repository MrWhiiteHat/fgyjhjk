"""Training callbacks: early stopping, checkpointing, CSV logging, LR tracking."""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Dict, Optional

import torch

from training.utils.checkpoint import save_checkpoint


class EarlyStopping:
    """Stop training when monitored metric does not improve for a patience window."""

    def __init__(self, patience: int, min_delta: float, maximize: bool) -> None:
        self.patience = int(max(1, patience))
        self.min_delta = float(min_delta)
        self.maximize = bool(maximize)
        self.best_score: Optional[float] = None
        self.counter = 0
        self.should_stop = False

    def step(self, score: float) -> bool:
        """Update stopping state and return whether training should stop."""
        if self.best_score is None:
            self.best_score = float(score)
            self.counter = 0
            return False

        if self.maximize:
            improved = float(score) > float(self.best_score) + self.min_delta
        else:
            improved = float(score) < float(self.best_score) - self.min_delta

        if improved:
            self.best_score = float(score)
            self.counter = 0
            self.should_stop = False
            return False

        self.counter += 1
        self.should_stop = self.counter >= self.patience
        return self.should_stop


class ModelCheckpoint:
    """Save best and last checkpoints with complete training state dictionaries."""

    def __init__(
        self,
        checkpoint_dir: Path,
        monitor_metric: str,
        maximize_metric: bool,
        save_best_only: bool,
        save_last_checkpoint: bool,
        logger: logging.Logger,
    ) -> None:
        self.checkpoint_dir = checkpoint_dir
        self.monitor_metric = str(monitor_metric)
        self.maximize_metric = bool(maximize_metric)
        self.save_best_only = bool(save_best_only)
        self.save_last_checkpoint = bool(save_last_checkpoint)
        self.logger = logger

        self.best_metric: Optional[float] = None
        self.best_epoch: Optional[int] = None
        self.best_path: Optional[Path] = None
        self.last_path: Optional[Path] = None

        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def _is_improved(self, metric: float) -> bool:
        """Check if current metric improves over previous best metric."""
        if self.best_metric is None:
            return True
        if self.maximize_metric:
            return float(metric) > float(self.best_metric)
        return float(metric) < float(self.best_metric)

    def step(self, state: Dict, metric: float, epoch: int) -> Dict[str, str | bool | float | int | None]:
        """Save best/last checkpoint(s) and return checkpoint operation status."""
        improved = self._is_improved(metric)

        if improved:
            self.best_metric = float(metric)
            self.best_epoch = int(epoch)
            self.best_path = self.checkpoint_dir / "best_model.pt"
            save_checkpoint(self.best_path, state, self.logger)

        if self.save_last_checkpoint:
            self.last_path = self.checkpoint_dir / "last_model.pt"
            save_checkpoint(self.last_path, state, self.logger)

        if not self.save_best_only:
            epoch_path = self.checkpoint_dir / f"epoch_{int(epoch):03d}.pt"
            save_checkpoint(epoch_path, state, self.logger)

        return {
            "improved": improved,
            "best_metric": self.best_metric,
            "best_epoch": self.best_epoch,
            "best_path": str(self.best_path) if self.best_path else "",
            "last_path": str(self.last_path) if self.last_path else "",
        }


class CSVHistoryLogger:
    """CSV logger to persist epoch-level metrics history."""

    def __init__(self, csv_path: Path) -> None:
        self.csv_path = csv_path
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        self.header_written = self.csv_path.exists() and self.csv_path.stat().st_size > 0

    def log(self, metrics: Dict) -> None:
        """Append one epoch metrics row to CSV file."""
        fieldnames = list(metrics.keys())

        with self.csv_path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            if not self.header_written:
                writer.writeheader()
                self.header_written = True
            writer.writerow(metrics)


class LearningRateTracker:
    """Utility callback for tracking optimizer learning rates over time."""

    def get_current_lrs(self, optimizer: torch.optim.Optimizer) -> Dict[str, float]:
        """Return current LR values for each optimizer parameter group."""
        output: Dict[str, float] = {}
        for idx, group in enumerate(optimizer.param_groups):
            output[f"lr_group_{idx}"] = float(group.get("lr", 0.0))
        return output
