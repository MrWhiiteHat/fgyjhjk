"""Deterministic preprocessing adapter for evaluation and inference runtime."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np
import torch

from evaluation.utils.io import safe_read_image


@dataclass
class PreprocessResult:
    """Container for preprocessing output and metadata."""

    tensor: Optional[torch.Tensor]
    status: str
    error_message: str
    metadata: Dict[str, Any]


class InferencePreprocessor:
    """Apply deterministic inference transforms consistent with training-time normalization.

    This adapter intentionally avoids random augmentations to keep evaluation and inference
    reproducible and leakage-safe.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        face_crop_hook: Optional[Callable[[np.ndarray], Optional[np.ndarray]]] = None,
    ) -> None:
        self.config = config
        self.input_size = int(config.get("input_size", 224))
        self.mean = np.asarray(config.get("mean", [0.485, 0.456, 0.406]), dtype=np.float32)
        self.std = np.asarray(config.get("std", [0.229, 0.224, 0.225]), dtype=np.float32)
        self.preprocessing_mode = str(config.get("preprocessing_mode", "resize")).strip().lower()
        self.center_crop_size = int(config.get("center_crop_size", self.input_size))
        self.face_crop_required = bool(config.get("face_crop_required", False))
        self.face_crop_hook = face_crop_hook

        if self.mean.shape[0] != 3 or self.std.shape[0] != 3:
            raise ValueError("Mean/std must contain exactly 3 values for RGB channels")

    def describe(self) -> Dict[str, Any]:
        """Return deterministic preprocessing configuration details."""
        return {
            "input_size": self.input_size,
            "mean": self.mean.tolist(),
            "std": self.std.tolist(),
            "preprocessing_mode": self.preprocessing_mode,
            "center_crop_size": self.center_crop_size,
            "face_crop_required": self.face_crop_required,
            "has_face_crop_hook": self.face_crop_hook is not None,
            "uses_random_augmentation": False,
        }

    def preprocess_image_path(self, image_path: str | Path) -> PreprocessResult:
        """Load image from disk and preprocess into normalized CHW float tensor."""
        image, error = safe_read_image(image_path)
        if error is not None or image is None:
            return PreprocessResult(
                tensor=None,
                status="error",
                error_message=error or "Unknown image read error",
                metadata={"input_path": str(Path(image_path).as_posix())},
            )

        result = self.preprocess_numpy_image(
            image=image,
            assume_bgr=True,
            input_id=str(Path(image_path).as_posix()),
        )
        return result

    def preprocess_numpy_image(
        self,
        image: np.ndarray,
        assume_bgr: bool = True,
        input_id: str = "numpy_input",
    ) -> PreprocessResult:
        """Preprocess an in-memory numpy image into normalized CHW float tensor."""
        if image is None:
            return PreprocessResult(
                tensor=None,
                status="error",
                error_message="Input numpy image is None",
                metadata={"input_id": input_id},
            )

        if image.size == 0:
            return PreprocessResult(
                tensor=None,
                status="error",
                error_message="Input numpy image is empty",
                metadata={"input_id": input_id},
            )

        try:
            rgb_image = self._to_rgb(image=image, assume_bgr=assume_bgr)
            cropped = self._apply_optional_face_crop(rgb_image)
            transformed = self._apply_spatial_ops(cropped)
            tensor = self._to_normalized_tensor(transformed)
        except Exception as exc:
            return PreprocessResult(
                tensor=None,
                status="error",
                error_message=f"Preprocessing failed: {exc}",
                metadata={"input_id": input_id},
            )

        return PreprocessResult(
            tensor=tensor,
            status="ok",
            error_message="",
            metadata={
                "input_id": input_id,
                "height": int(transformed.shape[0]),
                "width": int(transformed.shape[1]),
                "channels": int(transformed.shape[2]),
            },
        )

    def preprocess_batch_numpy(
        self,
        images: Sequence[np.ndarray],
        assume_bgr: bool = True,
        input_ids: Optional[Sequence[str]] = None,
    ) -> Tuple[Optional[torch.Tensor], List[PreprocessResult]]:
        """Preprocess list of images and return stacked batch tensor for valid entries."""
        results: List[PreprocessResult] = []
        tensors: List[torch.Tensor] = []

        for index, image in enumerate(images):
            input_id = str(input_ids[index]) if input_ids and index < len(input_ids) else f"numpy_{index}"
            result = self.preprocess_numpy_image(image=image, assume_bgr=assume_bgr, input_id=input_id)
            results.append(result)
            if result.status == "ok" and result.tensor is not None:
                tensors.append(result.tensor)

        if not tensors:
            return None, results

        batch = torch.stack(tensors, dim=0)
        return batch, results

    def _to_rgb(self, image: np.ndarray, assume_bgr: bool) -> np.ndarray:
        """Convert grayscale/BGR/BGRA images to RGB format."""
        if image.ndim == 2:
            return np.repeat(image[:, :, None], 3, axis=2)

        if image.ndim != 3:
            raise ValueError(f"Unsupported image dimensions: {image.shape}")

        channels = image.shape[2]
        if channels == 1:
            return np.repeat(image, 3, axis=2)

        if channels == 4:
            if assume_bgr:
                return cv2.cvtColor(image, cv2.COLOR_BGRA2RGB)
            return cv2.cvtColor(image, cv2.COLOR_RGBA2RGB)

        if channels >= 3:
            first_three = image[:, :, :3]
            if assume_bgr:
                return cv2.cvtColor(first_three, cv2.COLOR_BGR2RGB)
            return first_three

        raise ValueError(f"Unable to process image channels: {channels}")

    def _apply_optional_face_crop(self, rgb_image: np.ndarray) -> np.ndarray:
        """Apply face crop hook when configured; fail clearly when required and unavailable."""
        if self.face_crop_hook is None:
            if self.face_crop_required:
                raise RuntimeError(
                    "face_crop_required=True but no face_crop_hook provided. "
                    "Provide a face crop hook or set face_crop_required=False."
                )
            return rgb_image

        cropped = self.face_crop_hook(rgb_image)
        if cropped is None or cropped.size == 0:
            if self.face_crop_required:
                raise RuntimeError("Face crop hook did not return a valid crop")
            return rgb_image
        return cropped

    def _apply_spatial_ops(self, rgb_image: np.ndarray) -> np.ndarray:
        """Apply deterministic resize/crop strategy for inference."""
        mode = self.preprocessing_mode

        if mode == "resize":
            return cv2.resize(rgb_image, (self.input_size, self.input_size), interpolation=cv2.INTER_LINEAR)

        if mode == "center_crop":
            return self._center_crop_or_resize(rgb_image, crop_size=self.center_crop_size)

        if mode == "resize_center_crop":
            resized = self._resize_shorter_side(rgb_image, short_side=max(self.input_size, self.center_crop_size))
            cropped = self._center_crop_or_resize(resized, crop_size=self.center_crop_size)
            return cv2.resize(cropped, (self.input_size, self.input_size), interpolation=cv2.INTER_LINEAR)

        if mode == "letterbox":
            return self._letterbox(rgb_image, target_size=self.input_size)

        raise ValueError(
            f"Unsupported preprocessing_mode='{self.preprocessing_mode}'. "
            "Supported modes: resize, center_crop, resize_center_crop, letterbox"
        )

    def _resize_shorter_side(self, image: np.ndarray, short_side: int) -> np.ndarray:
        """Resize image preserving aspect ratio by setting shorter side."""
        height, width = image.shape[:2]
        if height <= 0 or width <= 0:
            raise ValueError(f"Invalid image shape for resize: {image.shape}")

        if height < width:
            new_height = int(short_side)
            new_width = int(round((width / max(height, 1)) * short_side))
        else:
            new_width = int(short_side)
            new_height = int(round((height / max(width, 1)) * short_side))

        return cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_LINEAR)

    def _center_crop_or_resize(self, image: np.ndarray, crop_size: int) -> np.ndarray:
        """Center crop image to square crop_size; resize first if image is smaller."""
        height, width = image.shape[:2]
        size = int(crop_size)
        if size <= 0:
            raise ValueError("center_crop_size must be > 0")

        if min(height, width) < size:
            scale = float(size) / float(max(min(height, width), 1))
            new_width = int(round(width * scale))
            new_height = int(round(height * scale))
            image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
            height, width = image.shape[:2]

        y1 = max((height - size) // 2, 0)
        x1 = max((width - size) // 2, 0)
        y2 = y1 + size
        x2 = x1 + size
        return image[y1:y2, x1:x2]

    def _letterbox(self, image: np.ndarray, target_size: int) -> np.ndarray:
        """Resize image preserving ratio and pad to square target size."""
        height, width = image.shape[:2]
        target = int(target_size)
        scale = min(target / max(width, 1), target / max(height, 1))
        resized_width = int(round(width * scale))
        resized_height = int(round(height * scale))

        resized = cv2.resize(image, (resized_width, resized_height), interpolation=cv2.INTER_LINEAR)
        canvas = np.zeros((target, target, 3), dtype=resized.dtype)

        y_offset = (target - resized_height) // 2
        x_offset = (target - resized_width) // 2
        canvas[y_offset : y_offset + resized_height, x_offset : x_offset + resized_width] = resized
        return canvas

    def _to_normalized_tensor(self, rgb_image: np.ndarray) -> torch.Tensor:
        """Convert RGB uint8/float image to normalized tensor in CHW format."""
        image = rgb_image.astype(np.float32)
        if image.max() > 1.0:
            image = image / 255.0

        if image.ndim != 3 or image.shape[2] != 3:
            raise ValueError(f"Expected HWC RGB image after preprocessing, got shape={image.shape}")

        normalized = (image - self.mean[None, None, :]) / self.std[None, None, :]
        tensor = torch.from_numpy(normalized).permute(2, 0, 1).contiguous().float()
        return tensor
