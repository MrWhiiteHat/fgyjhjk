"""Checkpoint save/load helpers for training and inference."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import torch


def save_checkpoint(checkpoint_path: Path, state: Dict[str, Any], logger: logging.Logger) -> None:
    """Persist training state dictionary to disk."""
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(state, checkpoint_path)
    logger.info("Saved checkpoint: %s", checkpoint_path)


def load_checkpoint(
    checkpoint_path: Path,
    map_location: str | torch.device = "cpu",
    logger: Optional[logging.Logger] = None,
) -> Dict[str, Any]:
    """Load checkpoint dictionary with robust existence checks."""
    if not checkpoint_path.exists() or not checkpoint_path.is_file():
        raise FileNotFoundError(f"Checkpoint file does not exist: {checkpoint_path}")

    payload = torch.load(checkpoint_path, map_location=map_location)
    if not isinstance(payload, dict):
        raise ValueError(f"Checkpoint content must be dictionary: {checkpoint_path}")

    if logger:
        logger.info("Loaded checkpoint: %s", checkpoint_path)
    return payload


def resume_training_state(
    checkpoint_path: Path,
    model: torch.nn.Module,
    optimizer: Optional[torch.optim.Optimizer],
    scheduler: Optional[Any],
    scaler: Optional[torch.amp.GradScaler],
    logger: logging.Logger,
    strict: bool = True,
) -> Dict[str, Any]:
    """Resume model and optimizer/scheduler/scaler states from checkpoint."""
    checkpoint = load_checkpoint(checkpoint_path, map_location="cpu", logger=logger)

    state_dict = checkpoint.get("model_state_dict")
    if state_dict is None:
        raise KeyError("Checkpoint missing 'model_state_dict' for resume")

    model.load_state_dict(state_dict, strict=strict)

    if optimizer is not None and checkpoint.get("optimizer_state_dict") is not None:
        optimizer.load_state_dict(checkpoint["optimizer_state_dict"])

    if scheduler is not None and checkpoint.get("scheduler_state_dict") is not None:
        scheduler.load_state_dict(checkpoint["scheduler_state_dict"])

    if scaler is not None and checkpoint.get("scaler_state_dict") is not None:
        scaler.load_state_dict(checkpoint["scaler_state_dict"])

    resume_info = {
        "start_epoch": int(checkpoint.get("epoch", -1)) + 1,
        "best_metric": checkpoint.get("best_metric", None),
        "best_epoch": checkpoint.get("best_epoch", None),
        "threshold": checkpoint.get("threshold", None),
        "checkpoint": checkpoint,
    }

    logger.info(
        "Resumed state from checkpoint '%s' at epoch=%d",
        checkpoint_path,
        resume_info["start_epoch"],
    )
    return resume_info


def load_model_for_inference(
    model: torch.nn.Module,
    checkpoint_path: Path,
    map_location: str | torch.device = "cpu",
    strict: bool = True,
    logger: Optional[logging.Logger] = None,
) -> torch.nn.Module:
    """Load trained model weights for inference from checkpoint path."""
    checkpoint = load_checkpoint(checkpoint_path, map_location=map_location, logger=logger)

    state_dict = checkpoint.get("model_state_dict", checkpoint)
    if not isinstance(state_dict, dict):
        raise ValueError(f"Model state dict is invalid in checkpoint: {checkpoint_path}")

    model.load_state_dict(state_dict, strict=strict)
    model.eval()

    if logger:
        logger.info("Model loaded for inference from: %s", checkpoint_path)
    return model
