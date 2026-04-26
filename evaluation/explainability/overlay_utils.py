"""Utilities for explainability heatmap rendering and image overlays."""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

import cv2
import numpy as np


def normalize_heatmap(heatmap: np.ndarray, eps: float = 1e-8) -> np.ndarray:
    """Normalize heatmap to [0, 1] with robust denominator handling."""
    data = np.asarray(heatmap, dtype=np.float32)
    min_value = float(np.min(data))
    max_value = float(np.max(data))
    denom = max(max_value - min_value, eps)
    normalized = (data - min_value) / denom
    return np.clip(normalized, 0.0, 1.0)


def colorize_heatmap(heatmap: np.ndarray, colormap: int = cv2.COLORMAP_JET) -> np.ndarray:
    """Convert normalized heatmap into RGB colormap representation."""
    normalized = normalize_heatmap(heatmap)
    uint8_map = np.uint8(np.round(normalized * 255.0))
    colored_bgr = cv2.applyColorMap(uint8_map, colormap)
    colored_rgb = cv2.cvtColor(colored_bgr, cv2.COLOR_BGR2RGB)
    return colored_rgb


def overlay_heatmap_on_image(
    image_rgb: np.ndarray,
    heatmap: np.ndarray,
    alpha: float = 0.45,
) -> np.ndarray:
    """Overlay heatmap on RGB image."""
    if image_rgb.ndim != 3 or image_rgb.shape[2] != 3:
        raise ValueError(f"Expected RGB image with shape [H,W,3], got {image_rgb.shape}")

    h, w = image_rgb.shape[:2]
    normalized = normalize_heatmap(heatmap)
    resized = cv2.resize(normalized, (w, h), interpolation=cv2.INTER_LINEAR)
    colored = colorize_heatmap(resized)

    base = image_rgb.astype(np.float32)
    overlay = colored.astype(np.float32)
    blended = (1.0 - float(alpha)) * base + float(alpha) * overlay
    return np.clip(blended, 0.0, 255.0).astype(np.uint8)


def save_rgb_image(path: str | Path, image_rgb: np.ndarray) -> Path:
    """Save RGB image to disk using OpenCV-safe BGR conversion."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
    success = cv2.imwrite(str(output), bgr)
    if not success:
        raise RuntimeError(f"Failed to save image at path: {output}")
    return output


def stack_explainability_triplet(
    original_rgb: np.ndarray,
    heatmap: np.ndarray,
    overlay_rgb: np.ndarray,
    title_left: str = "Original",
    title_mid: str = "Heatmap",
    title_right: str = "Overlay",
) -> np.ndarray:
    """Create horizontal panel image with original, heatmap, and overlay."""
    h, w = original_rgb.shape[:2]
    resized_heat = cv2.resize(normalize_heatmap(heatmap), (w, h), interpolation=cv2.INTER_LINEAR)
    heat_rgb = colorize_heatmap(resized_heat)

    panel = np.concatenate([original_rgb, heat_rgb, overlay_rgb], axis=1)

    # Draw compact labels at the top of each panel section.
    font = cv2.FONT_HERSHEY_SIMPLEX
    color = (255, 255, 255)
    thickness = 1
    cv2.putText(panel, title_left, (10, 25), font, 0.7, color, thickness, cv2.LINE_AA)
    cv2.putText(panel, title_mid, (w + 10, 25), font, 0.7, color, thickness, cv2.LINE_AA)
    cv2.putText(panel, title_right, (2 * w + 10, 25), font, 0.7, color, thickness, cv2.LINE_AA)

    return panel


def draw_prediction_overlay(
    image_bgr: np.ndarray,
    predicted_label: str,
    probability: float,
    threshold: float,
    inference_time_ms: float,
) -> np.ndarray:
    """Draw compact prediction details onto a BGR frame for inference outputs."""
    frame = image_bgr.copy()
    color = (0, 0, 255) if str(predicted_label).strip().upper() == "FAKE" else (0, 180, 0)

    overlay_lines = [
        f"Label: {predicted_label}",
        f"Prob(fake): {probability:.4f}",
        f"Threshold: {threshold:.2f}",
        f"Inference: {inference_time_ms:.2f} ms",
    ]

    font = cv2.FONT_HERSHEY_SIMPLEX
    y = 30
    for line in overlay_lines:
        cv2.putText(frame, line, (10, y), font, 0.65, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(frame, line, (10, y), font, 0.65, color, 1, cv2.LINE_AA)
        y += 28

    return frame
