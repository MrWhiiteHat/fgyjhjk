"""Centralized IO utilities for evaluation, inference, and reporting."""

from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import cv2
import numpy as np
import pandas as pd

from evaluation.utils.helpers import ensure_dir, normalize_extensions


def timestamp_for_filename() -> str:
    """Return compact timestamp string safe for filenames."""
    return time.strftime("%Y%m%d_%H%M%S", time.localtime())


def sanitize_filename(name: str, replacement: str = "_") -> str:
    """Replace unsafe filename characters with a safe replacement token."""
    raw = str(name).strip()
    if not raw:
        return "unnamed"
    safe = re.sub(r"[^A-Za-z0-9._-]", replacement, raw)
    safe = re.sub(r"_+", "_", safe).strip("._")
    return safe or "unnamed"


def is_supported_extension(path: str | Path, allowed_extensions: Sequence[str]) -> bool:
    """Check file extension against normalized allow-list."""
    extensions = set(normalize_extensions(allowed_extensions))
    suffix = Path(path).suffix.lower()
    return suffix in extensions


def safe_read_image(path: str | Path) -> Tuple[Optional[np.ndarray], Optional[str]]:
    """Read image safely, including Windows paths, returning (image, error)."""
    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        return None, f"Image file does not exist: {file_path}"

    try:
        buffer = np.fromfile(str(file_path), dtype=np.uint8)
        if buffer.size == 0:
            return None, f"Image file is empty: {file_path}"
        image = cv2.imdecode(buffer, cv2.IMREAD_UNCHANGED)
        if image is None:
            return None, f"Failed to decode image bytes: {file_path}"
        return image, None
    except Exception as exc:
        return None, f"Image read failure for {file_path}: {exc}"


def safe_open_video(path: str | Path) -> Tuple[Optional[cv2.VideoCapture], Optional[str]]:
    """Open video capture safely and validate open status."""
    video_path = Path(path)
    if not video_path.exists() or not video_path.is_file():
        return None, f"Video file does not exist: {video_path}"

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        capture.release()
        return None, f"Unable to open video stream: {video_path}"

    return capture, None


def safe_video_writer(
    output_path: str | Path,
    fps: float,
    frame_width: int,
    frame_height: int,
    codec: str = "mp4v",
) -> Tuple[Optional[cv2.VideoWriter], Optional[str]]:
    """Create a video writer and return writer or error message."""
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if fps <= 0:
        fps = 25.0

    fourcc = cv2.VideoWriter_fourcc(*codec)
    writer = cv2.VideoWriter(str(out_path), fourcc, float(fps), (int(frame_width), int(frame_height)))
    if not writer.isOpened():
        writer.release()
        return None, f"Failed to open video writer for path: {out_path}"
    return writer, None


def gather_files_recursive(root_dir: str | Path, allowed_extensions: Sequence[str]) -> List[Path]:
    """Recursively collect files with extensions from a root directory."""
    root = Path(root_dir)
    if not root.exists() or not root.is_dir():
        return []

    allowed = set(normalize_extensions(allowed_extensions))
    collected: List[Path] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in allowed:
            collected.append(path)
    return collected


def ensure_output_structure(base_output_dir: str | Path) -> Dict[str, Path]:
    """Create and return mandatory output subdirectories."""
    base = ensure_dir(base_output_dir)
    structure = {
        "metrics": base / "metrics",
        "predictions": base / "predictions",
        "reports": base / "reports",
        "explainability": base / "explainability",
        "confusion_matrices": base / "confusion_matrices",
        "roc_pr_curves": base / "roc_pr_curves",
        "calibrated_outputs": base / "calibrated_outputs",
        "failure_cases": base / "failure_cases",
    }

    for path in structure.values():
        path.mkdir(parents=True, exist_ok=True)

    return structure


def save_dataframe_csv(table: pd.DataFrame, path: str | Path) -> Path:
    """Save dataframe as CSV using UTF-8 encoding."""
    csv_path = Path(path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(csv_path, index=False, encoding="utf-8")
    return csv_path


def save_records_json(records: List[Dict[str, Any]], path: str | Path, indent: int = 2) -> Path:
    """Save list-of-dictionaries records to JSON."""
    json_path = Path(path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(records, handle, ensure_ascii=True, indent=indent)
    return json_path


def save_dict_json(payload: Dict[str, Any], path: str | Path, indent: int = 2) -> Path:
    """Save dictionary payload to JSON."""
    json_path = Path(path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True, indent=indent)
    return json_path


def copy_file_safe(
    source_path: str | Path,
    destination_path: str | Path,
    overwrite: bool = True,
) -> Tuple[Optional[Path], Optional[str]]:
    """Copy file safely, creating destination directories as needed."""
    src = Path(source_path)
    dst = Path(destination_path)

    if not src.exists() or not src.is_file():
        return None, f"Source file does not exist: {src}"

    if dst.exists() and not overwrite:
        return dst, None

    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(src, dst)
        return dst, None
    except Exception as exc:
        return None, f"Copy failed from {src} to {dst}: {exc}"


def write_text(path: str | Path, content: str) -> Path:
    """Write text content to disk."""
    txt_path = Path(path)
    txt_path.parent.mkdir(parents=True, exist_ok=True)
    with txt_path.open("w", encoding="utf-8") as handle:
        handle.write(content)
    return txt_path


def save_key_value_lines(path: str | Path, values: Dict[str, Any]) -> Path:
    """Write key-value lines to a plain text file."""
    lines = [f"{key}: {value}" for key, value in values.items()]
    return write_text(path, "\n".join(lines) + "\n")


def to_serializable(value: Any) -> Any:
    """Convert numpy scalar/array values into JSON-serializable values."""
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: to_serializable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_serializable(v) for v in value]
    return value


def save_serializable_json(payload: Dict[str, Any], path: str | Path, indent: int = 2) -> Path:
    """Save dictionary after converting common non-serializable values."""
    serializable = to_serializable(payload)
    return save_dict_json(serializable, path=path, indent=indent)


def safe_relpath(path: str | Path, root: str | Path) -> str:
    """Return relative path string when possible, else fallback to absolute."""
    target = Path(path)
    base = Path(root)
    try:
        return str(target.resolve().relative_to(base.resolve()).as_posix())
    except Exception:
        return str(target.as_posix())


def collect_all_files_recursive(root_dir: str | Path) -> List[Path]:
    """Collect every file recursively for scan/report purposes."""
    root = Path(root_dir)
    if not root.exists() or not root.is_dir():
        return []
    return [path for path in sorted(root.rglob("*")) if path.is_file()]


def safe_int(value: Any, default: int = 0) -> int:
    """Convert value to int with default fallback."""
    try:
        return int(value)
    except Exception:
        return int(default)


def safe_float(value: Any, default: float = 0.0) -> float:
    """Convert value to float with default fallback."""
    try:
        return float(value)
    except Exception:
        return float(default)
