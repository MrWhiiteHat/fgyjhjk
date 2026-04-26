"""General helper utilities for the training pipeline."""

from __future__ import annotations

import json
import logging
import math
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
import yaml
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score


def ensure_dir(path: Path | str) -> Path:
    """Create directory if needed and return normalized Path object."""
    resolved = Path(path)
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def ensure_dirs(paths: Iterable[Path | str]) -> List[Path]:
    """Create many directories and return resulting Path objects."""
    return [ensure_dir(path) for path in paths]


def load_yaml(path: Path | str) -> Dict:
    """Load a YAML file into a dictionary."""
    yaml_path = Path(path)
    if not yaml_path.exists():
        raise FileNotFoundError(f"YAML config file not found: {yaml_path}")

    with yaml_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)

    if not isinstance(payload, dict):
        raise ValueError(f"YAML config must contain a dictionary: {yaml_path}")
    return payload


def save_yaml(payload: Dict, path: Path | str) -> None:
    """Write dictionary payload to YAML file."""
    yaml_path = Path(path)
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    with yaml_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False)


def save_json(payload: Dict, path: Path | str, indent: int = 2) -> None:
    """Write dictionary payload to JSON file."""
    json_path = Path(path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True, indent=indent)


def format_seconds(total_seconds: float) -> str:
    """Format seconds as human-readable HH:MM:SS."""
    total = int(max(0, round(total_seconds)))
    hours = total // 3600
    minutes = (total % 3600) // 60
    seconds = total % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def now_utc_timestamp() -> str:
    """Return compact UTC timestamp string for experiment artifacts."""
    return time.strftime("%Y%m%d_%H%M%S", time.gmtime())


def flatten_dict(data: Dict, parent_key: str = "", sep: str = ".") -> Dict:
    """Flatten nested dictionaries using dot-separated keys."""
    flattened: Dict = {}
    for key, value in data.items():
        new_key = f"{parent_key}{sep}{key}" if parent_key else str(key)
        if isinstance(value, dict):
            flattened.update(flatten_dict(value, parent_key=new_key, sep=sep))
        else:
            flattened[new_key] = value
    return flattened


def compute_class_distribution(labels: Sequence[int]) -> Dict[int, int]:
    """Compute class counts for integer binary labels."""
    counts = {0: 0, 1: 0}
    for label in labels:
        label_int = int(label)
        if label_int in counts:
            counts[label_int] += 1
    return counts


def check_split_leakage(
    train_paths: Sequence[str],
    val_paths: Sequence[str],
    test_paths: Sequence[str],
) -> Tuple[bool, Dict[str, int]]:
    """Check whether filepaths overlap across train/val/test splits."""
    train_set = set(train_paths)
    val_set = set(val_paths)
    test_set = set(test_paths)

    overlap_train_val = len(train_set & val_set)
    overlap_train_test = len(train_set & test_set)
    overlap_val_test = len(val_set & test_set)

    leakage = (overlap_train_val + overlap_train_test + overlap_val_test) > 0
    details = {
        "train_val": overlap_train_val,
        "train_test": overlap_train_test,
        "val_test": overlap_val_test,
    }
    return leakage, details


def sweep_threshold(
    y_true: Sequence[int],
    y_prob: Sequence[float],
    metric_name: str,
    min_threshold: float,
    max_threshold: float,
    step: float,
    maximize: bool = True,
) -> Tuple[float, float]:
    """Find threshold maximizing or minimizing a metric over validation probabilities."""
    if len(y_true) == 0:
        return 0.5, float("nan")

    y_true_np = np.asarray(y_true, dtype=np.int64)
    y_prob_np = np.asarray(y_prob, dtype=np.float64)

    if step <= 0:
        raise ValueError("Threshold sweep step must be > 0")
    if min_threshold >= max_threshold:
        raise ValueError("Threshold sweep min must be < max")

    metric = metric_name.strip().lower()
    best_threshold = float(min_threshold)
    best_score = -math.inf if maximize else math.inf

    threshold = float(min_threshold)
    while threshold <= float(max_threshold) + 1e-12:
        predictions = (y_prob_np >= threshold).astype(np.int64)

        if metric == "f1":
            score = float(f1_score(y_true_np, predictions, zero_division=0))
        elif metric == "balanced_accuracy":
            score = float(balanced_accuracy_score(y_true_np, predictions))
        elif metric == "accuracy":
            score = float(accuracy_score(y_true_np, predictions))
        else:
            raise ValueError(f"Unsupported threshold metric: {metric_name}")

        is_better = score > best_score if maximize else score < best_score
        if is_better:
            best_score = score
            best_threshold = threshold

        threshold = round(threshold + step, 10)

    return float(best_threshold), float(best_score)


def validate_output_artifacts(
    logger: logging.Logger,
    expected_paths: Dict[str, Path],
) -> Dict[str, bool]:
    """Validate output artifact existence and return checklist status map."""
    results: Dict[str, bool] = {}
    for key, artifact_path in expected_paths.items():
        exists = artifact_path.exists()
        results[key] = exists
        if exists:
            logger.info("Artifact check passed: %s -> %s", key, artifact_path)
        else:
            logger.warning("Artifact check failed: %s -> %s", key, artifact_path)
    return results
