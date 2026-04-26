"""Shared utilities for preprocessing module."""

from __future__ import annotations

import csv
import json
import logging
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import cv2
import numpy as np
import yaml

REAL_LABEL = 0
FAKE_LABEL = 1


@dataclass
class SampleRecord:
    """Single input sample record built from split metadata."""

    split: str
    filepath: str
    label: int
    dataset: str


def load_config(config_path: str) -> Dict:
    """Load preprocessing YAML config into dictionary."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file does not exist: {path}")

    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)

    if not isinstance(payload, dict):
        raise ValueError("Preprocessing config must contain a top-level dictionary")
    return payload


def ensure_required_output_structure(config: Dict) -> None:
    """Create strict output directory structure required for Module 2."""
    required_dirs = [
        "dataset/preprocessed/train/real",
        "dataset/preprocessed/train/fake",
        "dataset/preprocessed/val/real",
        "dataset/preprocessed/val/fake",
        "dataset/preprocessed/test/real",
        "dataset/preprocessed/test/fake",
        "dataset/face_crops/real",
        "dataset/face_crops/fake",
        "dataset/face_landmarks/real",
        "dataset/face_landmarks/fake",
        "dataset/rejected/blurry",
        "dataset/rejected/no_face",
        "dataset/rejected/multi_face",
        "dataset/rejected/corrupted",
        "dataset/rejected/duplicates",
        "dataset/metadata",
        "dataset/logs",
    ]

    for folder in required_dirs:
        Path(folder).mkdir(parents=True, exist_ok=True)


def setup_logger(log_file: Path) -> logging.Logger:
    """Create module logger for preprocessing pipeline."""
    logger = logging.getLogger("preprocessing_pipeline")
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    log_file.parent.mkdir(parents=True, exist_ok=True)

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
    return logger


def safe_imread(file_path: Path) -> Optional[np.ndarray]:
    """Read image safely from path including unicode paths."""
    try:
        if not file_path.exists() or not file_path.is_file():
            return None
        encoded = np.fromfile(str(file_path), dtype=np.uint8)
        if encoded.size == 0:
            return None
        image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        return image
    except Exception:
        return None


def safe_imwrite(file_path: Path, image: np.ndarray, quality: int = 95) -> bool:
    """Write image safely to disk and create parent directories automatically."""
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        ext = file_path.suffix.lower()

        if ext in {".jpg", ".jpeg"}:
            params = [int(cv2.IMWRITE_JPEG_QUALITY), max(1, min(100, quality))]
        elif ext == ".png":
            params = [int(cv2.IMWRITE_PNG_COMPRESSION), 3]
        else:
            params = []

        success, encoded = cv2.imencode(ext if ext else ".jpg", image, params)
        if not success:
            return False

        with file_path.open("wb") as handle:
            handle.write(encoded.tobytes())
        return True
    except Exception:
        return False


def safe_read_media_frame(
    file_path: Path,
    allowed_image_extensions: Sequence[str],
    allowed_video_extensions: Sequence[str],
) -> Optional[np.ndarray]:
    """Read a representative frame from image or video file paths."""
    suffix = file_path.suffix.lower()
    image_exts = {ext.lower() for ext in allowed_image_extensions}
    video_exts = {ext.lower() for ext in allowed_video_extensions}

    if suffix in image_exts:
        return safe_imread(file_path)

    if suffix in video_exts:
        try:
            capture = cv2.VideoCapture(str(file_path))
            if not capture.isOpened():
                return None

            ok, frame = capture.read()
            capture.release()

            if not ok or frame is None or frame.size == 0:
                return None
            return frame
        except Exception:
            return None

    return None


def is_supported_media(
    file_path: Path,
    allowed_image_extensions: Sequence[str],
    allowed_video_extensions: Sequence[str],
) -> bool:
    """Validate whether path extension belongs to allowed image or video formats."""
    suffix = file_path.suffix.lower()
    image_exts = {ext.lower() for ext in allowed_image_extensions}
    video_exts = {ext.lower() for ext in allowed_video_extensions}
    return suffix in image_exts or suffix in video_exts


def label_to_name(label: int) -> str:
    """Convert integer label to canonical class name."""
    return "real" if int(label) == REAL_LABEL else "fake"


def load_split_samples(config: Dict) -> List[SampleRecord]:
    """Load train/val/test sample rows and convert to records."""
    result: List[SampleRecord] = []

    split_paths = {
        "train": Path(config["train_csv_path"]),
        "val": Path(config["val_csv_path"]),
        "test": Path(config["test_csv_path"]),
    }

    for split_name, csv_path in split_paths.items():
        if not csv_path.exists():
            continue

        with csv_path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                try:
                    record = SampleRecord(
                        split=split_name,
                        filepath=str(row["filepath"]).strip(),
                        label=int(row["label"]),
                        dataset=str(row.get("dataset", "unknown")).strip() or "unknown",
                    )
                except Exception:
                    continue
                result.append(record)

    return result


def write_csv_dicts(csv_path: Path, rows: Sequence[Dict], header: Sequence[str]) -> None:
    """Write dictionaries to CSV in deterministic order using provided header."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(header))
        writer.writeheader()
        for row in rows:
            payload = {key: row.get(key, "") for key in header}
            writer.writerow(payload)


def relative_to_dataset_root(path: Path) -> str:
    """Convert path to dataset-relative string when possible."""
    dataset_root = Path("dataset").resolve()
    try:
        return path.resolve().relative_to(dataset_root).as_posix()
    except Exception:
        return path.as_posix()


def stringify_landmarks(landmarks: Optional[Dict[str, Tuple[float, float]]]) -> str:
    """Serialize landmarks dictionary to compact JSON string."""
    if not landmarks:
        return ""
    return json.dumps(landmarks, separators=(",", ":"), ensure_ascii=True)


def save_landmarks_json(path: Path, payload: Dict) -> None:
    """Persist landmarks payload to JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True, indent=2)


def clamp_bbox(
    bbox: Sequence[float],
    image_shape: Sequence[int],
    margin_ratio: float = 0.0,
) -> Tuple[int, int, int, int]:
    """Clamp bbox to image dimensions and optionally expand by margin ratio."""
    height, width = int(image_shape[0]), int(image_shape[1])
    x1, y1, x2, y2 = [float(value) for value in bbox]

    if margin_ratio > 0:
        box_w = max(1.0, x2 - x1)
        box_h = max(1.0, y2 - y1)
        margin_x = box_w * margin_ratio
        margin_y = box_h * margin_ratio
        x1 -= margin_x
        y1 -= margin_y
        x2 += margin_x
        y2 += margin_y

    x1 = int(max(0, min(width - 1, round(x1))))
    y1 = int(max(0, min(height - 1, round(y1))))
    x2 = int(max(0, min(width, round(x2))))
    y2 = int(max(0, min(height, round(y2))))

    if x2 <= x1:
        x2 = min(width, x1 + 1)
    if y2 <= y1:
        y2 = min(height, y1 + 1)

    return x1, y1, x2, y2


def sample_id_from_record(split: str, filepath: str) -> str:
    """Generate deterministic sample id from split and source filepath."""
    normalized = f"{split}::{filepath}".replace("\\", "/")
    return str(abs(hash(normalized)))


def copy_to_rejected(source_path: Path, rejected_root: Path, reason: str, filename: str) -> Path:
    """Copy source sample into reason-specific rejected folder."""
    destination_dir = rejected_root / reason
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / filename

    if destination.exists():
        stem = destination.stem
        suffix = destination.suffix
        counter = 1
        while destination.exists():
            destination = destination_dir / f"{stem}_{counter}{suffix}"
            counter += 1

    shutil.copy2(source_path, destination)
    return destination


def now_ms() -> int:
    """Return current time in milliseconds for profiling fields."""
    return int(time.time() * 1000)
