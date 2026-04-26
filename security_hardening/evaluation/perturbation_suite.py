"""Perturbation suite for robustness evaluation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

try:
    import cv2  # type: ignore
except Exception:  # noqa: BLE001
    cv2 = None


@dataclass
class PerturbationCase:
    """Single perturbation case descriptor."""

    name: str
    image: np.ndarray


class PerturbationSuite:
    """Generates perturbation variants used for robustness testing."""

    def run(self, image: np.ndarray) -> list[PerturbationCase]:
        """Create standard perturbation cases from source image."""

        source = image.astype(np.uint8)
        cases = [
            PerturbationCase(name="mild_noise", image=self._mild_noise(source)),
            PerturbationCase(name="blur", image=self._blur(source)),
            PerturbationCase(name="compression", image=self._compression(source)),
            PerturbationCase(name="crop", image=self._crop(source)),
            PerturbationCase(name="brightness_shift", image=self._brightness_shift(source)),
            PerturbationCase(name="patch_like", image=self._patch_like(source)),
        ]
        return cases

    @staticmethod
    def _mild_noise(image: np.ndarray) -> np.ndarray:
        """Apply mild gaussian-like noise."""

        rng = np.random.default_rng(7)
        noise = rng.normal(0.0, 8.0, size=image.shape)
        return np.clip(image.astype(np.float32) + noise, 0, 255).astype(np.uint8)

    @staticmethod
    def _blur(image: np.ndarray) -> np.ndarray:
        """Apply gaussian blur."""

        if cv2 is None:
            return image
        return cv2.GaussianBlur(image, (5, 5), 0)

    @staticmethod
    def _compression(image: np.ndarray) -> np.ndarray:
        """Apply JPEG compression degradation."""

        if cv2 is None:
            return image
        ok, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 45])
        if not ok:
            return image
        decoded = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        return decoded if decoded is not None else image

    @staticmethod
    def _crop(image: np.ndarray) -> np.ndarray:
        """Apply center crop and resize back to original size."""

        h, w = image.shape[:2]
        crop_h = max(1, int(h * 0.85))
        crop_w = max(1, int(w * 0.85))
        top = max(0, (h - crop_h) // 2)
        left = max(0, (w - crop_w) // 2)
        cropped = image[top : top + crop_h, left : left + crop_w]
        if cv2 is None:
            return image
        return cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)

    @staticmethod
    def _brightness_shift(image: np.ndarray) -> np.ndarray:
        """Apply moderate brightness increase."""

        return np.clip(image.astype(np.float32) * 1.12 + 8.0, 0, 255).astype(np.uint8)

    @staticmethod
    def _patch_like(image: np.ndarray) -> np.ndarray:
        """Inject localized patch-like perturbation."""

        out = image.copy()
        h, w = out.shape[:2]
        ph = max(8, h // 6)
        pw = max(8, w // 6)
        top = h // 3
        left = w // 3
        out[top : top + ph, left : left + pw] = np.clip(out[top : top + ph, left : left + pw] + 70, 0, 255)
        return out.astype(np.uint8)
