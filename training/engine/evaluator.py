"""Validation/test evaluator for binary model metrics and predictions."""

from __future__ import annotations

import csv
import logging
from contextlib import nullcontext
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import torch
from torch.utils.data import DataLoader

from training.engine.metrics import EpochMetricTracker


def save_predictions_csv(
    output_path: Path,
    filepaths: list[str],
    labels: np.ndarray,
    logits: np.ndarray,
    probabilities: np.ndarray,
    threshold: float,
    split: str,
) -> None:
    """Write per-sample predictions with required schema."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    predicted_labels = (probabilities >= float(threshold)).astype(np.int64)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "filepath",
            "true_label",
            "predicted_logit",
            "predicted_probability",
            "predicted_label",
            "split",
        ])

        for idx, path in enumerate(filepaths):
            writer.writerow(
                [
                    path,
                    int(labels[idx]),
                    float(logits[idx]),
                    float(probabilities[idx]),
                    int(predicted_labels[idx]),
                    split,
                ]
            )


def evaluate_model(
    model: torch.nn.Module,
    dataloader: DataLoader,
    criterion: torch.nn.Module,
    device: torch.device,
    threshold: float,
    use_amp: bool,
    split: str,
    predictions_path: Path,
    logger: logging.Logger,
) -> Tuple[Dict, Dict]:
    """Run evaluation loop and return aggregate metrics plus raw outputs."""
    model.eval()
    tracker = EpochMetricTracker(split_name=split)

    autocast_ctx = torch.cuda.amp.autocast if use_amp and device.type == "cuda" else nullcontext

    with torch.no_grad():
        for batch in dataloader:
            images = batch["image"].to(device, non_blocking=True)
            labels = batch["label"].to(device, non_blocking=True).float().view(-1)
            filepaths = batch["filepath"]

            with autocast_ctx():
                logits = model(images).view(-1)
                loss = criterion(logits, labels)

            tracker.update(
                loss=float(loss.detach().item()),
                logits=logits.detach().cpu().numpy(),
                labels=labels.detach().cpu().numpy(),
                filepaths=filepaths,
            )

    metrics, raw_outputs = tracker.compute(threshold=float(threshold))

    save_predictions_csv(
        output_path=predictions_path,
        filepaths=raw_outputs["filepaths"],
        labels=raw_outputs["labels"],
        logits=raw_outputs["logits"],
        probabilities=raw_outputs["probabilities"],
        threshold=float(threshold),
        split=split,
    )

    logger.info("Evaluation complete for split=%s | size=%d | loss=%.6f", split, len(raw_outputs["labels"]), metrics["loss"])
    return metrics, raw_outputs
