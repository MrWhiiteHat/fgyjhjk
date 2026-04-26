"""Logging helpers for experiment tracking."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict

from .helpers import flatten_dict


def get_experiment_logger(experiment_name: str, log_dir: Path) -> tuple[logging.Logger, Path]:
    """Create a logger that writes to both console and experiment log file."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{experiment_name}.log"

    logger_name = f"training.{experiment_name}"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger, log_file

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)

    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)
    logger.propagate = False
    return logger, log_file


def log_config(logger: logging.Logger, config: Dict) -> None:
    """Log flattened config values for reproducibility."""
    logger.info("Experiment configuration")
    flattened = flatten_dict(config)
    for key in sorted(flattened.keys()):
        logger.info("  %s: %s", key, flattened[key])
