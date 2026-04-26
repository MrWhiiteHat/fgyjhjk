"""Structured logging utilities for evaluation and inference scripts."""

from __future__ import annotations

import logging
import traceback
from pathlib import Path
from typing import Optional


def get_logger(
    name: str,
    log_dir: str | Path,
    log_level: str = "INFO",
    log_filename: Optional[str] = None,
) -> tuple[logging.Logger, Path]:
    """Create or fetch a script logger with console and file handlers."""
    resolved_dir = Path(log_dir)
    resolved_dir.mkdir(parents=True, exist_ok=True)

    level_name = str(log_level).strip().upper()
    level = getattr(logging, level_name, logging.INFO)

    filename = log_filename or f"{name}.log"
    log_path = resolved_dir / filename

    logger = logging.getLogger(f"evaluation.{name}")
    logger.setLevel(level)

    if logger.handlers:
        return logger, log_path

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)
    stream_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)
    logger.propagate = False

    return logger, log_path


def log_exception(logger: logging.Logger, message: str, exc: BaseException) -> None:
    """Log exception message and full traceback."""
    logger.error("%s | %s", message, exc)
    logger.error("Traceback:\n%s", traceback.format_exc())


class Timer:
    """Context manager for timed code sections."""

    def __init__(self, logger: logging.Logger, label: str) -> None:
        self.logger = logger
        self.label = label
        self.start_time: float = 0.0

    def __enter__(self) -> "Timer":
        import time

        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, exc_tb) -> None:
        import time

        elapsed_ms = (time.perf_counter() - self.start_time) * 1000.0
        self.logger.info("%s completed in %.2f ms", self.label, elapsed_ms)
