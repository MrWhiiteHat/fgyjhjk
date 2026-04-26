"""Device management helpers for CPU/CUDA execution."""

from __future__ import annotations

import logging
from typing import Any

import torch


def resolve_device(requested_device: str, logger: logging.Logger) -> torch.device:
    """Resolve configured device string to torch.device with graceful fallback."""
    requested = str(requested_device).strip().lower()

    if requested == "auto":
        if torch.cuda.is_available():
            device = torch.device("cuda")
        else:
            device = torch.device("cpu")
    elif requested == "cuda":
        if torch.cuda.is_available():
            device = torch.device("cuda")
        else:
            logger.warning("CUDA requested but not available. Falling back to CPU.")
            device = torch.device("cpu")
    elif requested == "cpu":
        device = torch.device("cpu")
    else:
        logger.warning("Unknown device '%s'. Falling back to auto.", requested_device)
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    logger.info("Selected device: %s", device)
    if device.type == "cuda":
        logger.info("CUDA device count: %d", torch.cuda.device_count())
        logger.info("CUDA device name: %s", torch.cuda.get_device_name(0))
    return device


def should_use_amp(config_use_amp: bool, device: torch.device, logger: logging.Logger) -> bool:
    """Enable AMP only when CUDA is available and requested."""
    use_amp = bool(config_use_amp) and device.type == "cuda"
    if bool(config_use_amp) and device.type != "cuda":
        logger.warning("AMP requested but CUDA unavailable. AMP disabled.")
    logger.info("Mixed precision AMP enabled: %s", use_amp)
    return use_amp


def move_to_device(batch: Any, device: torch.device) -> Any:
    """Recursively move tensors in nested batch structures to target device."""
    if torch.is_tensor(batch):
        return batch.to(device, non_blocking=True)
    if isinstance(batch, dict):
        return {key: move_to_device(value, device) for key, value in batch.items()}
    if isinstance(batch, (list, tuple)):
        moved = [move_to_device(item, device) for item in batch]
        return type(batch)(moved)
    return batch
