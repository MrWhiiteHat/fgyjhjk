"""Safe preprocessing transforms for robust inference input handling."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import numpy as np
from PIL import Image

try:
    import cv2  # type: ignore
except Exception:  # noqa: BLE001
    cv2 = None


@dataclass
class SafePreprocessConfig:
    """Toggleable preprocessing controls and parameters."""

    enable_resize_normalization: bool = True
    enable_mild_denoise: bool = True
    enable_safe_recompression: bool = True
    target_max_side: int = 1024
    denoise_strength: int = 3
    jpeg_quality: int = 90


@dataclass
class PreprocessResult:
    """Output of safe preprocessing with tradeoff metadata."""

    image: np.ndarray
    metadata: dict[str, str]


class SafePreprocessor:
    """Applies defensive transforms while preserving model fidelity where possible."""

    def __init__(self, config: SafePreprocessConfig | None = None) -> None:
        self.config = config or SafePreprocessConfig()

    def process(self, image: np.ndarray) -> PreprocessResult:
        """Apply configured preprocessing transforms and return transformed image."""

        arr = self._validate_channels(image)
        metadata: dict[str, str] = {
            "channel_validation": "applied",
            "robustness_accuracy_tradeoff": (
                "mild denoise and recompression can improve robustness against perturbations but may slightly "
                "reduce fidelity on borderline cases"
            ),
        }

        if self.config.enable_resize_normalization:
            arr = self._resize_normalize(arr, max_side=self.config.target_max_side)
            metadata["resize_normalization"] = "enabled"
        else:
            metadata["resize_normalization"] = "disabled"

        if self.config.enable_mild_denoise:
            arr = self._mild_denoise(arr)
            metadata["mild_denoise"] = "enabled"
        else:
            metadata["mild_denoise"] = "disabled"

        if self.config.enable_safe_recompression:
            arr = self._safe_recompress(arr, quality=self.config.jpeg_quality)
            metadata["safe_recompression"] = "enabled"
        else:
            metadata["safe_recompression"] = "disabled"

        return PreprocessResult(image=arr, metadata=metadata)

    @staticmethod
    def _validate_channels(image: np.ndarray) -> np.ndarray:
        """Validate and normalize channel layout to 3-channel RGB."""

        arr = np.asarray(image)
        if arr.ndim == 2:
            arr = np.stack([arr, arr, arr], axis=2)
        elif arr.ndim == 3 and arr.shape[2] == 1:
            arr = np.repeat(arr, 3, axis=2)
        elif arr.ndim == 3 and arr.shape[2] == 4:
            arr = arr[:, :, :3]
        elif arr.ndim != 3 or arr.shape[2] != 3:
            raise ValueError("Invalid color channels")

        return arr.astype(np.uint8)

    @staticmethod
    def _resize_normalize(image: np.ndarray, max_side: int) -> np.ndarray:
        """Resize image while preserving aspect ratio."""

        h, w = image.shape[:2]
        current_max = max(h, w)
        if current_max <= max_side:
            return image

        scale = float(max_side) / float(current_max)
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))

        pil = Image.fromarray(image)
        resized = pil.resize((new_w, new_h), Image.Resampling.BILINEAR)
        return np.array(resized, dtype=np.uint8)

    def _mild_denoise(self, image: np.ndarray) -> np.ndarray:
        """Apply mild denoising with OpenCV fallback behavior."""

        if cv2 is None:
            return image

        denoised = cv2.fastNlMeansDenoisingColored(
            image,
            None,
            h=max(1, int(self.config.denoise_strength)),
            hColor=max(1, int(self.config.denoise_strength)),
            templateWindowSize=7,
            searchWindowSize=21,
        )
        return denoised.astype(np.uint8)

    @staticmethod
    def _safe_recompress(image: np.ndarray, quality: int) -> np.ndarray:
        """Recompress image with controlled JPEG quality."""

        quality = int(min(max(quality, 50), 100))
        buffer = BytesIO()
        Image.fromarray(image).save(buffer, format="JPEG", quality=quality, optimize=True)
        buffer.seek(0)
        output = Image.open(buffer).convert("RGB")
        return np.array(output, dtype=np.uint8)
