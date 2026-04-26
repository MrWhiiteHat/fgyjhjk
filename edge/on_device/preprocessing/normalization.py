"""Shared normalization and tensor-formatting helpers for edge runtimes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np


@dataclass(frozen=True)
class NormalizationConfig:
    """Normalization settings matching server-side preprocessing."""

    mean: tuple[float, float, float]
    std: tuple[float, float, float]


DEFAULT_NORMALIZATION = NormalizationConfig(
    mean=(0.485, 0.456, 0.406),
    std=(0.229, 0.224, 0.225),
)


def normalize_image(image: np.ndarray, config: NormalizationConfig = DEFAULT_NORMALIZATION) -> np.ndarray:
    """Normalize HWC RGB float image in range [0, 1] using channel-wise mean/std."""
    if image.ndim != 3 or image.shape[-1] != 3:
        raise ValueError("Expected image shape [H, W, 3]")
    mean = np.asarray(config.mean, dtype=np.float32).reshape(1, 1, 3)
    std = np.asarray(config.std, dtype=np.float32).reshape(1, 1, 3)
    return (image.astype(np.float32) - mean) / std


def denormalize_image(image: np.ndarray, config: NormalizationConfig = DEFAULT_NORMALIZATION) -> np.ndarray:
    """Invert normalization for visualization only."""
    mean = np.asarray(config.mean, dtype=np.float32).reshape(1, 1, 3)
    std = np.asarray(config.std, dtype=np.float32).reshape(1, 1, 3)
    restored = image.astype(np.float32) * std + mean
    return np.clip(restored, 0.0, 1.0)


def to_nchw_batch(image_hwc: np.ndarray) -> np.ndarray:
    """Convert single normalized HWC image into NCHW batch tensor."""
    if image_hwc.ndim != 3 or image_hwc.shape[-1] != 3:
        raise ValueError("Expected normalized HWC tensor with 3 channels")
    return np.transpose(image_hwc, (2, 0, 1))[None, ...].astype(np.float32)


def to_nhwc_batch(image_hwc: np.ndarray) -> np.ndarray:
    """Convert single normalized HWC image into NHWC batch tensor."""
    if image_hwc.ndim != 3 or image_hwc.shape[-1] != 3:
        raise ValueError("Expected normalized HWC tensor with 3 channels")
    return image_hwc[None, ...].astype(np.float32)


def safe_probability(value: float) -> float:
    """Clamp value into probability range [0, 1]."""
    return float(max(0.0, min(1.0, value)))
