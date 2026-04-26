"""Device utilities for robust CPU/CUDA inference behavior."""

from __future__ import annotations

import logging

import torch


def resolve_device(requested_device: str, logger: logging.Logger) -> torch.device:
    """Resolve configured device with graceful fallback logic."""
    requested = str(requested_device).strip().lower()

    if requested == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    elif requested == "cuda":
        if torch.cuda.is_available():
            device = torch.device("cuda")
        else:
            logger.warning("CUDA requested but unavailable. Falling back to CPU.")
            device = torch.device("cpu")
    elif requested == "cpu":
        device = torch.device("cpu")
    else:
        logger.warning("Unsupported device value '%s'. Falling back to auto.", requested_device)
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    logger.info("Selected device: %s", device)
    if device.type == "cuda":
        logger.info("CUDA device count: %d", torch.cuda.device_count())
        logger.info("CUDA primary device: %s", torch.cuda.get_device_name(0))

    return device


def can_use_amp(config_amp_enabled: bool, device: torch.device, logger: logging.Logger) -> bool:
    """Enable automatic mixed precision only when safe and requested."""
    requested = bool(config_amp_enabled)
    use_amp = requested and device.type == "cuda"
    if requested and device.type != "cuda":
        logger.warning("AMP requested but CUDA is unavailable. AMP disabled.")
    logger.info("AMP enabled for inference: %s", use_amp)
    return use_amp


def sync_device_if_needed(device: torch.device) -> None:
    """Synchronize CUDA stream for stable latency measurement."""
    if device.type == "cuda":
        torch.cuda.synchronize(device=device)
