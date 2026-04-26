"""Reproducibility utilities for random seed control."""

from __future__ import annotations

import logging
import os
import random

import numpy as np
import torch


def set_global_seed(seed: int, logger: logging.Logger, deterministic: bool = True) -> None:
    """Set Python, NumPy, and PyTorch seeds for reproducible training behavior."""
    seed_value = int(seed)

    random.seed(seed_value)
    np.random.seed(seed_value)
    torch.manual_seed(seed_value)
    torch.cuda.manual_seed_all(seed_value)

    os.environ["PYTHONHASHSEED"] = str(seed_value)

    if deterministic:
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
        try:
            torch.use_deterministic_algorithms(True, warn_only=True)
        except Exception:
            pass
        logger.info(
            "Seed set to %d with deterministic mode enabled (more reproducible, potentially slower)",
            seed_value,
        )
    else:
        torch.backends.cudnn.deterministic = False
        torch.backends.cudnn.benchmark = True
        logger.info(
            "Seed set to %d with non-deterministic mode (faster, less reproducible)",
            seed_value,
        )
