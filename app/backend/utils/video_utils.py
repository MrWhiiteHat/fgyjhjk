"""Video utility helpers for backend metadata extraction."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import cv2


def read_video_metadata(path: str | Path) -> Dict[str, float]:
    """Read basic video metadata (fps, frame_count, resolution)."""
    target = Path(path)
    capture = cv2.VideoCapture(str(target))
    if not capture.isOpened():
        raise ValueError(f"Unable to open video file: {target}")

    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    capture.release()

    return {
        "fps": fps,
        "frame_count": frame_count,
        "width": width,
        "height": height,
    }
