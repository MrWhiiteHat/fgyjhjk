"""Image quality checks for preprocessing pipeline."""

from __future__ import annotations

from typing import Dict, Tuple

import cv2
import numpy as np


def blur_score(image_bgr: np.ndarray) -> float:
    """Compute Laplacian variance as blur sharpness score."""
    if image_bgr is None or image_bgr.size == 0:
        return 0.0
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def brightness_score(image_bgr: np.ndarray) -> float:
    """Compute brightness score using mean grayscale intensity."""
    if image_bgr is None or image_bgr.size == 0:
        return 0.0
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    return float(np.mean(gray))


def evaluate_quality(
    image_bgr: np.ndarray,
    blur_threshold: float,
    brightness_min: float,
    brightness_max: float,
) -> Tuple[bool, str, Dict[str, float]]:
    """Validate image quality and return pass/fail reason and metrics."""
    metrics = {
        "blur_score": blur_score(image_bgr),
        "brightness": brightness_score(image_bgr),
        "width": float(image_bgr.shape[1] if image_bgr is not None and image_bgr.ndim == 3 else 0.0),
        "height": float(image_bgr.shape[0] if image_bgr is not None and image_bgr.ndim == 3 else 0.0),
    }

    if image_bgr is None or image_bgr.size == 0:
        return False, "corrupted", metrics

    if metrics["blur_score"] < float(blur_threshold):
        return False, "blurry", metrics

    if metrics["brightness"] < float(brightness_min) or metrics["brightness"] > float(brightness_max):
        return False, "blurry", metrics

    return True, "", metrics
