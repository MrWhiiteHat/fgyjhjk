"""Normalization utilities for preprocessed face tensors."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np


def normalize_image(
    image_rgb: np.ndarray,
    mean: Sequence[float],
    std: Sequence[float],
) -> np.ndarray:
    """Normalize RGB image into CHW float tensor using mean/std vectors."""
    if image_rgb is None or image_rgb.size == 0:
        raise ValueError("Cannot normalize empty image")

    image_float = image_rgb.astype(np.float32) / 255.0
    mean_arr = np.array(mean, dtype=np.float32).reshape(1, 1, 3)
    std_arr = np.array(std, dtype=np.float32).reshape(1, 1, 3)

    std_arr = np.where(std_arr == 0.0, 1.0, std_arr)
    normalized = (image_float - mean_arr) / std_arr

    chw = np.transpose(normalized, (2, 0, 1)).astype(np.float32)
    return chw


def save_tensor(path: Path, tensor: np.ndarray, use_fp16: bool = False) -> None:
    """Persist normalized tensor as NPY file."""
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = tensor.astype(np.float16) if use_fp16 else tensor.astype(np.float32)
    np.save(str(path), payload)
