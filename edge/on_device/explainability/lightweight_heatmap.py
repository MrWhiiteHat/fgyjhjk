"""Lightweight, device-friendly confidence-region visualization helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class HeatmapResult:
    """Output heatmap artifact and metadata."""

    heatmap: np.ndarray
    method: str
    note: str


def _normalize_map(values: np.ndarray) -> np.ndarray:
    values = values.astype(np.float32)
    v_min = float(values.min())
    v_max = float(values.max())
    if v_max <= v_min:
        return np.zeros_like(values, dtype=np.float32)
    return (values - v_min) / (v_max - v_min)


def build_lightweight_heatmap(image_rgb: np.ndarray) -> HeatmapResult:
    """Generate simple saliency-like map based on intensity gradients.

    This is a heuristic visualization and not a true gradient attribution like Grad-CAM.
    """
    if image_rgb.ndim != 3 or image_rgb.shape[-1] != 3:
        raise ValueError("Expected image RGB tensor [H, W, 3]")

    gray = (0.299 * image_rgb[..., 0] + 0.587 * image_rgb[..., 1] + 0.114 * image_rgb[..., 2]).astype(np.float32)
    gx = np.abs(np.diff(gray, axis=1, append=gray[:, -1:]))
    gy = np.abs(np.diff(gray, axis=0, append=gray[-1:, :]))
    energy = _normalize_map(gx + gy)

    return HeatmapResult(
        heatmap=energy,
        method="gradient_energy_heuristic",
        note="Heuristic on-device map; use backend explainability for stronger attribution confidence.",
    )


def overlay_heatmap(image_rgb: np.ndarray, heatmap: np.ndarray, alpha: float = 0.35) -> np.ndarray:
    """Overlay heatmap on top of original image."""
    alpha_value = max(0.0, min(1.0, float(alpha)))
    normalized = _normalize_map(heatmap)

    # Build a simple red-yellow color ramp.
    ramp = np.stack([
        normalized,
        normalized * 0.8,
        np.zeros_like(normalized),
    ], axis=-1)

    image = image_rgb.astype(np.float32) / 255.0
    blended = (1.0 - alpha_value) * image + alpha_value * ramp
    return np.clip(blended * 255.0, 0, 255).astype(np.uint8)


def save_overlay_image(output_path: str | Path, overlay_rgb: np.ndarray) -> str:
    """Save overlay image to disk using PIL fallback strategy."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    from PIL import Image

    Image.fromarray(overlay_rgb).save(path)
    return str(path.as_posix())
