"""Image utility helpers for backend validation and metadata extraction."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import cv2
import numpy as np


def read_image_metadata(path: str | Path) -> Dict[str, int]:
    """Read width/height/channels metadata from image path."""
    file_path = Path(path)
    buffer = np.fromfile(str(file_path), dtype=np.uint8)
    image = cv2.imdecode(buffer, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ValueError(f"Unable to decode image: {file_path}")

    if image.ndim == 2:
        height, width = image.shape
        channels = 1
    else:
        height, width = image.shape[:2]
        channels = image.shape[2]

    return {
        "width": int(width),
        "height": int(height),
        "channels": int(channels),
    }
