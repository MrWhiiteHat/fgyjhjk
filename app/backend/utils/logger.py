"""Structured logger configuration for backend services and API routes."""

from __future__ import annotations

import logging
from pathlib import Path


def configure_logger(name: str, level: str = "INFO", log_dir: str | Path | None = None) -> logging.Logger:
    """Create and return a logger with console and optional file handlers."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    resolved_level = getattr(logging, str(level).upper(), logging.INFO)
    logger.setLevel(resolved_level)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(resolved_level)
    logger.addHandler(stream_handler)

    if log_dir is not None:
        folder = Path(log_dir)
        folder.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(folder / f"{name.replace('.', '_')}.log", encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(resolved_level)
        logger.addHandler(file_handler)

    logger.propagate = False
    return logger
