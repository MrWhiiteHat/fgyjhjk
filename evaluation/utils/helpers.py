"""Shared helper utilities for the evaluation and inference layer."""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Sequence, Tuple

import numpy as np
import pandas as pd
import yaml


def ensure_dir(path: str | Path) -> Path:
    """Create directory if needed and return it as a Path."""
    resolved = Path(path)
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def ensure_dirs(paths: Iterable[str | Path]) -> List[Path]:
    """Create many directories and return normalized Path objects."""
    return [ensure_dir(path) for path in paths]


def load_yaml(path: str | Path) -> Dict[str, Any]:
    """Load YAML file and assert dictionary payload."""
    yaml_path = Path(path)
    if not yaml_path.exists():
        raise FileNotFoundError(f"YAML file not found: {yaml_path}")

    with yaml_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)

    if not isinstance(payload, dict):
        raise ValueError(f"YAML content must be a dictionary: {yaml_path}")
    return payload


def save_yaml(payload: Dict[str, Any], path: str | Path) -> Path:
    """Write dictionary payload to YAML file."""
    yaml_path = Path(path)
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    with yaml_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False)
    return yaml_path


def save_json(payload: Dict[str, Any], path: str | Path, indent: int = 2) -> Path:
    """Write dictionary payload to JSON with ASCII-safe output."""
    json_path = Path(path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True, indent=indent)
    return json_path


def save_text(text: str, path: str | Path) -> Path:
    """Write text payload to file."""
    txt_path = Path(path)
    txt_path.parent.mkdir(parents=True, exist_ok=True)
    with txt_path.open("w", encoding="utf-8") as handle:
        handle.write(text)
    return txt_path


def now_timestamp() -> str:
    """Return local timestamp string for artifact naming and plotting."""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def now_compact_timestamp() -> str:
    """Return compact timestamp string for filenames."""
    return time.strftime("%Y%m%d_%H%M%S", time.localtime())


def flatten_dict(data: Dict[str, Any], parent_key: str = "", sep: str = ".") -> Dict[str, Any]:
    """Flatten nested dictionary using dot-separated keys."""
    flattened: Dict[str, Any] = {}
    for key, value in data.items():
        new_key = f"{parent_key}{sep}{key}" if parent_key else str(key)
        if isinstance(value, dict):
            flattened.update(flatten_dict(value, parent_key=new_key, sep=sep))
        else:
            flattened[new_key] = value
    return flattened


def chunked(items: Sequence[Any], chunk_size: int) -> Iterator[Sequence[Any]]:
    """Yield fixed-size slices from a sequence."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    for start_idx in range(0, len(items), chunk_size):
        yield items[start_idx : start_idx + chunk_size]


def safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safely divide and return default when denominator is zero."""
    if abs(float(denominator)) < 1e-12:
        return float(default)
    return float(numerator) / float(denominator)


def to_probability_from_logit(logit: np.ndarray | float) -> np.ndarray | float:
    """Convert logits to probabilities using a numerically stable sigmoid."""
    if isinstance(logit, np.ndarray):
        clipped = np.clip(logit.astype(np.float64), -60.0, 60.0)
        return 1.0 / (1.0 + np.exp(-clipped))
    clipped_scalar = float(max(min(float(logit), 60.0), -60.0))
    return 1.0 / (1.0 + math.exp(-clipped_scalar))


def normalize_extensions(extensions: Sequence[str]) -> List[str]:
    """Normalize extension list to lowercase with leading dots."""
    normalized: List[str] = []
    for ext in extensions:
        value = str(ext).strip().lower()
        if not value:
            continue
        if not value.startswith("."):
            value = f".{value}"
        normalized.append(value)
    return sorted(set(normalized))


def class_index_to_name(index: int, class_names: Sequence[str]) -> str:
    """Map class index to configured display name."""
    if 0 <= int(index) < len(class_names):
        return str(class_names[int(index)])
    return str(index)


def class_name_to_index(name: str, class_names: Sequence[str]) -> int:
    """Map class name to integer index using case-insensitive matching."""
    target = str(name).strip().lower()
    for idx, class_name in enumerate(class_names):
        if str(class_name).strip().lower() == target:
            return int(idx)
    raise KeyError(f"Class name '{name}' not found in class_names={list(class_names)}")


def read_optional_csv(path: str | Path) -> pd.DataFrame:
    """Read CSV if path exists; otherwise return empty dataframe."""
    csv_path = Path(path)
    if not csv_path.exists() or not csv_path.is_file():
        return pd.DataFrame()
    try:
        return pd.read_csv(csv_path)
    except Exception:
        return pd.DataFrame()


def format_ms(milliseconds: float) -> str:
    """Format milliseconds as fixed-width string."""
    return f"{float(milliseconds):.2f}"


@dataclass
class RuntimeStats:
    """Container for aggregate runtime information."""

    count: int
    total_ms: float
    avg_ms: float
    min_ms: float
    max_ms: float


def summarize_latencies(latencies_ms: Sequence[float]) -> RuntimeStats:
    """Compute aggregate runtime statistics from latency values."""
    if not latencies_ms:
        return RuntimeStats(count=0, total_ms=0.0, avg_ms=0.0, min_ms=0.0, max_ms=0.0)

    lat_np = np.asarray(latencies_ms, dtype=np.float64)
    return RuntimeStats(
        count=int(lat_np.size),
        total_ms=float(np.sum(lat_np)),
        avg_ms=float(np.mean(lat_np)),
        min_ms=float(np.min(lat_np)),
        max_ms=float(np.max(lat_np)),
    )


def _to_normalized_path_string(path: str | Path) -> str:
    """Normalize path string for robust merge/join operations."""
    return str(Path(path).as_posix()).strip().lower()


def infer_label_from_path(path: str | Path) -> int:
    """Infer binary label from filepath folders when explicit labels are absent."""
    value = str(Path(path).as_posix()).lower()
    if "/fake/" in value or value.endswith("/fake"):
        return 1
    if "/real/" in value or value.endswith("/real"):
        return 0
    raise ValueError(f"Unable to infer label from path: {path}")


def collect_split_samples(
    split_name: str,
    split_dir: str | Path,
    metadata_csv: str | Path,
    image_extensions: Sequence[str],
) -> pd.DataFrame:
    """Collect split samples from metadata CSV with safe directory fallback."""
    split_key = str(split_name).strip().lower()
    normalized_exts = set(normalize_extensions(image_extensions))
    records: List[Dict[str, Any]] = []

    metadata_path = Path(metadata_csv)
    metadata_table = read_optional_csv(metadata_path)

    if not metadata_table.empty and {"split", "preprocessed_path"}.issubset(set(metadata_table.columns)):
        filtered = metadata_table[metadata_table["split"].astype(str).str.lower() == split_key].copy()
        for _, row in filtered.iterrows():
            raw_path = str(row.get("preprocessed_path", "")).strip()
            if not raw_path:
                continue

            file_path = Path(raw_path)
            if not file_path.is_absolute():
                file_path = Path(raw_path)

            if file_path.suffix.lower() not in normalized_exts:
                continue

            if not file_path.exists() or not file_path.is_file():
                continue

            label_value = row.get("label", row.get("true_label", None))
            try:
                label = int(label_value)
            except Exception:
                text = str(label_value).strip().lower()
                if text == "real":
                    label = 0
                elif text == "fake":
                    label = 1
                else:
                    try:
                        label = infer_label_from_path(file_path)
                    except Exception:
                        continue

            if label not in (0, 1):
                continue

            records.append(
                {
                    "filepath": str(file_path.as_posix()),
                    "true_label": int(label),
                    "split": split_key,
                    "dataset": str(row.get("dataset", "unknown")),
                    "source_filepath": str(row.get("source_filepath", "")),
                    "blur_score": row.get("blur_score", np.nan),
                    "brightness": row.get("brightness", np.nan),
                }
            )

    if records:
        return pd.DataFrame(records)

    # Fallback: infer from split directory real/fake subfolders.
    split_path = Path(split_dir)
    if not split_path.exists() or not split_path.is_dir():
        return pd.DataFrame(columns=["filepath", "true_label", "split", "dataset", "source_filepath", "blur_score", "brightness"])

    for class_name, label in (("real", 0), ("fake", 1)):
        class_dir = split_path / class_name
        if not class_dir.exists() or not class_dir.is_dir():
            continue
        for file_path in sorted(class_dir.rglob("*")):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in normalized_exts:
                continue
            records.append(
                {
                    "filepath": str(file_path.as_posix()),
                    "true_label": int(label),
                    "split": split_key,
                    "dataset": "unknown",
                    "source_filepath": "",
                    "blur_score": np.nan,
                    "brightness": np.nan,
                }
            )

    return pd.DataFrame(records)


def merge_optional_metadata(
    predictions: pd.DataFrame,
    metadata_csv: str | Path,
    preprocessing_report_csv: str | Path | None = None,
) -> pd.DataFrame:
    """Merge metadata tables into predictions using normalized path keys when possible."""
    result = predictions.copy()
    if result.empty:
        return result

    result["_norm_path"] = result["filepath"].apply(_to_normalized_path_string)

    metadata_table = read_optional_csv(metadata_csv)
    if not metadata_table.empty:
        if "preprocessed_path" in metadata_table.columns:
            metadata_table = metadata_table.copy()
            metadata_table["_norm_path"] = metadata_table["preprocessed_path"].apply(_to_normalized_path_string)
            keep_columns = [
                col
                for col in ["_norm_path", "dataset", "split", "source_filepath", "blur_score", "brightness"]
                if col in metadata_table.columns
            ]
            if keep_columns:
                result = result.merge(metadata_table[keep_columns], on="_norm_path", how="left", suffixes=("", "_meta"))

    if preprocessing_report_csv is not None:
        report_table = read_optional_csv(preprocessing_report_csv)
        if not report_table.empty:
            report = report_table.copy()
            path_col = "source_filepath" if "source_filepath" in report.columns else None
            if path_col is not None:
                report["_source_norm"] = report[path_col].apply(_to_normalized_path_string)
                if "source_filepath" in result.columns:
                    result["_source_norm"] = result["source_filepath"].apply(_to_normalized_path_string)
                    keep_cols = [
                        col
                        for col in ["_source_norm", "blur_score", "brightness", "dataset", "split"]
                        if col in report.columns
                    ]
                    if keep_cols:
                        result = result.merge(report[keep_cols], on="_source_norm", how="left", suffixes=("", "_report"))

    result = result.drop(columns=[col for col in ["_norm_path", "_source_norm"] if col in result.columns])
    return result
