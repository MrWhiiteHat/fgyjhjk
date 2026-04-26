"""Main training engine for robust binary classification experiments."""

from __future__ import annotations

import logging
import math
import time
from contextlib import nullcontext
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader
from tqdm import tqdm

from training.engine.callbacks import CSVHistoryLogger, EarlyStopping, LearningRateTracker, ModelCheckpoint
from training.engine.evaluator import evaluate_model
from training.engine.metrics import EpochMetricTracker, compute_binary_metrics
from training.engine.scheduler import SchedulerBundle, step_scheduler
from training.utils.checkpoint import resume_training_state
from training.utils.helpers import format_seconds, sweep_threshold


class Trainer:
    """Trainer encapsulating full epoch loop, validation, callbacks, and resume logic."""

    def __init__(
        self,
        model: torch.nn.Module,
        train_loader: DataLoader,
        val_loader: DataLoader,
        criterion: torch.nn.Module,
        optimizer: torch.optim.Optimizer,
        scheduler_bundle: SchedulerBundle,
        callbacks: Dict,
        device: torch.device,
        config: Dict,
        logger: logging.Logger,
        use_amp: bool,
    ) -> None:
        self.model = model
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.criterion = criterion
        self.optimizer = optimizer
        self.scheduler_bundle = scheduler_bundle
        self.callbacks = callbacks
        self.device = device
        self.config = config
        self.logger = logger
        self.use_amp = bool(use_amp)

        self.scaler = torch.cuda.amp.GradScaler(enabled=self.use_amp)

        self.start_epoch = 0
        self.best_threshold = float(config.get("threshold", 0.5))
        self.history_rows = []

        if device.type == "cuda" and torch.cuda.device_count() > 1:
            self.logger.info(
                "Multiple GPUs detected (%d). Current implementation uses single-device training.",
                torch.cuda.device_count(),
            )

        self._maybe_resume_from_checkpoint()

    def _maybe_resume_from_checkpoint(self) -> None:
        """Resume full training state when resume path is provided."""
        resume_path = str(self.config.get("resume_from_checkpoint", "")).strip()
        if not resume_path:
            return

        info = resume_training_state(
            checkpoint_path=Path(resume_path),
            model=self.model,
            optimizer=self.optimizer,
            scheduler=self.scheduler_bundle.scheduler,
            scaler=self.scaler if self.use_amp else None,
            logger=self.logger,
            strict=True,
        )

        self.start_epoch = int(info["start_epoch"])
        if info.get("threshold") is not None:
            self.best_threshold = float(info["threshold"])

        checkpoint_cb: ModelCheckpoint = self.callbacks["checkpoint"]
        if info.get("best_metric") is not None:
            checkpoint_cb.best_metric = float(info["best_metric"])
        if info.get("best_epoch") is not None:
            checkpoint_cb.best_epoch = int(info["best_epoch"])

    def _train_one_epoch(self, epoch: int) -> Dict:
        """Run one training epoch and return aggregated training metrics."""
        self.model.train()
        tracker = EpochMetricTracker(split_name="train")

        accumulation_steps = max(1, int(self.config.get("gradient_accumulation_steps", 1)))
        gradient_clip_norm = float(self.config.get("gradient_clip_norm", 0.0))

        self.optimizer.zero_grad(set_to_none=True)
        autocast_ctx = torch.cuda.amp.autocast if self.use_amp and self.device.type == "cuda" else nullcontext

        progress = tqdm(
            enumerate(self.train_loader),
            total=len(self.train_loader),
            desc=f"Train {epoch + 1}/{int(self.config['epochs'])}",
            leave=False,
        )

        for batch_idx, batch in progress:
            images = batch["image"].to(self.device, non_blocking=True)
            labels = batch["label"].to(self.device, non_blocking=True).float().view(-1)

            with autocast_ctx():
                logits = self.model(images).view(-1)
                loss = self.criterion(logits, labels)

            if not torch.isfinite(loss):
                raise FloatingPointError(
                    f"Non-finite loss encountered at epoch={epoch + 1} batch={batch_idx + 1}: {loss.item()}"
                )

            scaled_loss = loss / accumulation_steps
            self.scaler.scale(scaled_loss).backward()

            should_step = ((batch_idx + 1) % accumulation_steps == 0) or (batch_idx + 1 == len(self.train_loader))
            if should_step:
                if gradient_clip_norm > 0:
                    self.scaler.unscale_(self.optimizer)
                    torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=gradient_clip_norm)

                self.scaler.step(self.optimizer)
                self.scaler.update()
                self.optimizer.zero_grad(set_to_none=True)

                if self.scheduler_bundle.step_mode == "batch":
                    step_scheduler(self.scheduler_bundle)

            tracker.update(
                loss=float(loss.detach().item()),
                logits=logits.detach().cpu().numpy(),
                labels=labels.detach().cpu().numpy(),
                filepaths=batch["filepath"],
            )

            progress.set_postfix(loss=f"{loss.item():.4f}")

        train_metrics, _ = tracker.compute(threshold=float(self.best_threshold))
        return train_metrics

    def _maybe_sweep_threshold(self, val_outputs: Dict, val_metrics: Dict) -> Dict:
        """Optionally sweep decision threshold on validation outputs (no test leakage)."""
        sweep_cfg = self.config.get("threshold_sweep", {}) or {}
        if not bool(sweep_cfg.get("enabled", False)):
            val_metrics["threshold"] = float(self.best_threshold)
            return val_metrics

        metric_name = str(sweep_cfg.get("metric", "f1")).strip().lower()
        threshold_min = float(sweep_cfg.get("min", 0.1))
        threshold_max = float(sweep_cfg.get("max", 0.9))
        threshold_step = float(sweep_cfg.get("step", 0.02))

        best_threshold, best_threshold_score = sweep_threshold(
            y_true=val_outputs["labels"],
            y_prob=val_outputs["probabilities"],
            metric_name=metric_name,
            min_threshold=threshold_min,
            max_threshold=threshold_max,
            step=threshold_step,
            maximize=True,
        )

        self.best_threshold = float(best_threshold)
        tuned_metrics = compute_binary_metrics(
            y_true=val_outputs["labels"],
            y_prob=val_outputs["probabilities"],
            threshold=float(best_threshold),
        )
        tuned_metrics["loss"] = val_metrics["loss"]
        tuned_metrics["threshold"] = float(best_threshold)
        tuned_metrics["threshold_metric"] = metric_name
        tuned_metrics["threshold_metric_score"] = float(best_threshold_score)
        return tuned_metrics

    def train(self) -> Dict:
        """Execute full training and validation loop with callbacks."""
        total_start = time.time()

        early_stopping: EarlyStopping = self.callbacks["early_stopping"]
        checkpoint_cb: ModelCheckpoint = self.callbacks["checkpoint"]
        history_logger: CSVHistoryLogger = self.callbacks["history_logger"]
        lr_tracker: LearningRateTracker = self.callbacks["lr_tracker"]

        epochs = int(self.config.get("epochs", 1))
        predictions_dir = Path(self.config["predictions_dir"])
        predictions_dir.mkdir(parents=True, exist_ok=True)

        monitor_metric = str(self.config.get("monitor_metric", "val_f1"))

        epochs_completed = self.start_epoch
        failed = False

        for epoch in range(self.start_epoch, epochs):
            epoch_start = time.time()

            try:
                train_metrics = self._train_one_epoch(epoch)
            except FloatingPointError as exc:
                self.logger.error("Stopping training due to unrecoverable numeric error: %s", exc)
                failed = True
                break
            except Exception as exc:
                self.logger.error("Stopping training due to unrecoverable training error: %s", exc)
                failed = True
                break

            val_predictions_path = predictions_dir / f"val_epoch_{epoch + 1:03d}.csv"
            val_metrics, val_outputs = evaluate_model(
                model=self.model,
                dataloader=self.val_loader,
                criterion=self.criterion,
                device=self.device,
                threshold=float(self.best_threshold),
                use_amp=self.use_amp,
                split="val",
                predictions_path=val_predictions_path,
                logger=self.logger,
            )

            val_metrics = self._maybe_sweep_threshold(val_outputs, val_metrics)

            lr_values = lr_tracker.get_current_lrs(self.optimizer)
            epoch_time = time.time() - epoch_start

            epoch_row = {
                "epoch": epoch + 1,
                "train_loss": float(train_metrics["loss"]),
                "train_accuracy": float(train_metrics["accuracy"]),
                "train_precision": float(train_metrics["precision"]),
                "train_recall": float(train_metrics["recall"]),
                "train_f1": float(train_metrics["f1"]),
                "train_roc_auc": float(train_metrics["roc_auc"]),
                "train_pr_auc": float(train_metrics["pr_auc"]),
                "train_balanced_accuracy": float(train_metrics["balanced_accuracy"]),
                "val_loss": float(val_metrics["loss"]),
                "val_accuracy": float(val_metrics["accuracy"]),
                "val_precision": float(val_metrics["precision"]),
                "val_recall": float(val_metrics["recall"]),
                "val_f1": float(val_metrics["f1"]),
                "val_roc_auc": float(val_metrics["roc_auc"]),
                "val_pr_auc": float(val_metrics["pr_auc"]),
                "val_balanced_accuracy": float(val_metrics["balanced_accuracy"]),
                "threshold": float(val_metrics.get("threshold", self.best_threshold)),
                "epoch_time_sec": float(epoch_time),
            }
            epoch_row.update(lr_values)

            self.history_rows.append(epoch_row)
            history_logger.log(epoch_row)

            scheduler_monitor = str(self.config.get("scheduler_params", {}).get("monitor", "val_loss"))
            if self.scheduler_bundle.step_mode == "metric":
                metric_value = float(epoch_row.get(scheduler_monitor, epoch_row.get("val_loss", float("nan"))))
                step_scheduler(self.scheduler_bundle, metric_value=metric_value)
            elif self.scheduler_bundle.step_mode == "epoch":
                step_scheduler(self.scheduler_bundle)

            metric_value = epoch_row.get(monitor_metric)
            if metric_value is None:
                raise KeyError(f"Monitor metric '{monitor_metric}' not found in epoch metrics")

            state = {
                "epoch": epoch,
                "model_state_dict": self.model.state_dict(),
                "optimizer_state_dict": self.optimizer.state_dict(),
                "scheduler_state_dict": self.scheduler_bundle.scheduler.state_dict() if self.scheduler_bundle.scheduler else None,
                "scaler_state_dict": self.scaler.state_dict() if self.use_amp else None,
                "best_metric": checkpoint_cb.best_metric,
                "best_epoch": checkpoint_cb.best_epoch,
                "threshold": float(self.best_threshold),
                "config": self.config,
                "monitor_metric": monitor_metric,
            }

            checkpoint_info = checkpoint_cb.step(state=state, metric=float(metric_value), epoch=epoch + 1)

            self.logger.info(
                "Epoch %d/%d | train_loss=%.5f val_loss=%.5f val_f1=%.5f val_auc=%.5f threshold=%.3f time=%s improved=%s",
                epoch + 1,
                epochs,
                epoch_row["train_loss"],
                epoch_row["val_loss"],
                epoch_row["val_f1"],
                epoch_row["val_roc_auc"],
                epoch_row["threshold"],
                format_seconds(epoch_time),
                checkpoint_info["improved"],
            )

            epochs_completed = epoch + 1
            if early_stopping.step(float(metric_value)):
                self.logger.info("Early stopping triggered at epoch %d", epoch + 1)
                break

        total_time = time.time() - total_start
        history_df = pd.DataFrame(self.history_rows)

        return {
            "failed": failed,
            "epochs_completed": int(epochs_completed),
            "history": history_df,
            "best_epoch": checkpoint_cb.best_epoch,
            "best_metric": checkpoint_cb.best_metric,
            "best_checkpoint": str(checkpoint_cb.best_path) if checkpoint_cb.best_path else "",
            "last_checkpoint": str(checkpoint_cb.last_path) if checkpoint_cb.last_path else "",
            "threshold": float(self.best_threshold),
            "training_time_sec": float(total_time),
            "training_time_hms": format_seconds(total_time),
        }
