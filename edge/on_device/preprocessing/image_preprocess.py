"""Image preprocessing for edge inference with strict input validation."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np

from edge.on_device.preprocessing.normalization import (
    DEFAULT_NORMALIZATION,
    NormalizationConfig,
    normalize_image,
    to_nchw_batch,
    to_nhwc_batch,
)


def _load_with_pillow(path: Path) -> np.ndarray:
    from PIL import Image

    with Image.open(path) as image:
        rgb = image.convert("RGB")
        return np.asarray(rgb, dtype=np.uint8)


def _load_with_cv2(path: Path) -> np.ndarray:
    import cv2

    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Unable to decode image")
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def load_image_rgb(path: str | Path) -> np.ndarray:
    """Load image as RGB uint8 array from disk."""
    image_path = Path(path)
    if not image_path.exists() or not image_path.is_file():
        raise FileNotFoundError(f"Image not found: {image_path}")

    suffix = image_path.suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".gif"}:
        raise ValueError(f"Unsupported image extension: {suffix}")

    try:
        return _load_with_pillow(image_path)
    except Exception:
        return _load_with_cv2(image_path)


def resize_image(image_rgb: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    """Resize RGB image to target width/height."""
    width, height = int(size[0]), int(size[1])
    if width <= 0 or height <= 0:
        raise ValueError("Resize dimensions must be positive")

    try:
        from PIL import Image

        return np.asarray(Image.fromarray(image_rgb).resize((width, height)), dtype=np.uint8)
    except Exception:
        import cv2

        resized = cv2.resize(image_rgb, (width, height), interpolation=cv2.INTER_AREA)
        return resized.astype(np.uint8)


def center_crop(image_rgb: np.ndarray, crop_size: tuple[int, int]) -> np.ndarray:
    """Center crop RGB image if configured."""
    crop_w, crop_h = int(crop_size[0]), int(crop_size[1])
    h, w = image_rgb.shape[:2]
    if crop_w > w or crop_h > h:
        return image_rgb
    x0 = max(0, (w - crop_w) // 2)
    y0 = max(0, (h - crop_h) // 2)
    return image_rgb[y0 : y0 + crop_h, x0 : x0 + crop_w]


def preprocess_image_for_model(
    image_path: str | Path,
    input_size: tuple[int, int] = (224, 224),
    normalization: NormalizationConfig = DEFAULT_NORMALIZATION,
    use_center_crop: bool = False,
    tensor_layout: str = "nchw",
) -> np.ndarray:
    """Load and preprocess image for edge model inference."""
    image_rgb = load_image_rgb(image_path)
    if use_center_crop:
        image_rgb = center_crop(image_rgb, input_size)

    resized = resize_image(image_rgb, input_size).astype(np.float32) / 255.0
    normalized = normalize_image(resized, normalization)

    layout = tensor_layout.lower().strip()
    if layout == "nchw":
        return to_nchw_batch(normalized)
    if layout == "nhwc":
        return to_nhwc_batch(normalized)
    raise ValueError(f"Unsupported tensor layout: {tensor_layout}")
