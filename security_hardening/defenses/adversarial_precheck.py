"""Lightweight adversarial precheck before full inference."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

try:
    import cv2  # type: ignore
except Exception:  # noqa: BLE001
    cv2 = None


@dataclass
class AdversarialPrecheckConfig:
    """Configurable heuristic thresholds and weights."""

    noise_threshold: float = 24.0
    sharpen_threshold: float = 160.0
    micropattern_threshold: float = 0.35
    patch_threshold: float = 0.50
    weights: dict[str, float] = field(
        default_factory=lambda: {
            "noise": 0.25,
            "sharpen": 0.25,
            "micropattern": 0.25,
            "localized_patch": 0.25,
        }
    )


@dataclass
class PrecheckResult:
    """Precheck output with risk score and interpretable signal values."""

    risk_score: float
    suspicious: bool
    reason_codes: list[str]
    signals: dict[str, float]
    note: str


class AdversarialPrecheck:
    """Heuristic-based risk scoring for adversarial-like input patterns."""

    def __init__(self, config: AdversarialPrecheckConfig | None = None) -> None:
        self.config = config or AdversarialPrecheckConfig()

    def evaluate(self, image: np.ndarray) -> PrecheckResult:
        """Evaluate image and return bounded risk score and indicators."""

        if image.ndim not in {2, 3}:
            raise ValueError("Expected 2D grayscale or 3D color image")

        gray = self._to_gray(image)
        noise = self._noise_signal(gray)
        sharpen = self._sharpen_signal(gray)
        micropattern = self._micropattern_signal(gray)
        patch = self._localized_patch_signal(gray)

        normalized = {
            "noise": min(noise / max(self.config.noise_threshold, 1e-6), 2.0),
            "sharpen": min(sharpen / max(self.config.sharpen_threshold, 1e-6), 2.0),
            "micropattern": min(micropattern / max(self.config.micropattern_threshold, 1e-6), 2.0),
            "localized_patch": min(patch / max(self.config.patch_threshold, 1e-6), 2.0),
        }

        score = 0.0
        for key, weight in self.config.weights.items():
            score += float(weight) * min(max(normalized.get(key, 0.0), 0.0), 1.0)
        score = min(max(score, 0.0), 1.0)

        reason_codes: list[str] = []
        if noise >= self.config.noise_threshold:
            reason_codes.append("excessive_noise")
        if sharpen >= self.config.sharpen_threshold:
            reason_codes.append("suspicious_sharpening")
        if micropattern >= self.config.micropattern_threshold:
            reason_codes.append("repeated_micro_patterns")
        if patch >= self.config.patch_threshold:
            reason_codes.append("localized_patch_perturbation")

        return PrecheckResult(
            risk_score=score,
            suspicious=bool(reason_codes),
            reason_codes=reason_codes,
            signals={
                "noise_signal": noise,
                "sharpen_signal": sharpen,
                "micropattern_signal": micropattern,
                "localized_patch_signal": patch,
            },
            note="Heuristic precheck only; cannot guarantee complete adversarial detection.",
        )

    @staticmethod
    def _to_gray(image: np.ndarray) -> np.ndarray:
        """Convert input image to grayscale float32 representation."""

        arr = image.astype(np.float32)
        if arr.ndim == 2:
            return arr
        if arr.shape[2] == 1:
            return arr[:, :, 0]
        if cv2 is not None:
            return cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
        return np.mean(arr[:, :, :3], axis=2)

    @staticmethod
    def _noise_signal(gray: np.ndarray) -> float:
        """Estimate residual noise strength from denoised difference."""

        if cv2 is not None:
            smooth = cv2.GaussianBlur(gray, (3, 3), 0)
        else:
            smooth = gray
        residual = gray - smooth
        return float(np.std(residual))

    @staticmethod
    def _sharpen_signal(gray: np.ndarray) -> float:
        """Estimate sharpening artifacts through Laplacian variance."""

        if cv2 is not None:
            lap = cv2.Laplacian(gray, cv2.CV_32F)
        else:
            gx = np.diff(gray, axis=1, prepend=gray[:, :1])
            gy = np.diff(gray, axis=0, prepend=gray[:1, :])
            lap = gx + gy
        return float(np.var(lap))

    @staticmethod
    def _micropattern_signal(gray: np.ndarray) -> float:
        """Detect repeated micro-patterns using quantized patch diversity."""

        h, w = gray.shape
        if h < 8 or w < 8:
            return 0.0

        patches = []
        step = 4
        for row in range(0, h - 4, step):
            for col in range(0, w - 4, step):
                patch = gray[row : row + 4, col : col + 4]
                quantized = tuple(np.round(np.mean(patch) / 16.0, 0).astype(np.int32).reshape(-1)[:1])
                patches.append(quantized)
        if not patches:
            return 0.0
        unique_ratio = len(set(patches)) / len(patches)
        return float(1.0 - unique_ratio)

    @staticmethod
    def _localized_patch_signal(gray: np.ndarray) -> float:
        """Measure concentration of high-gradient energy in local windows."""

        gx = np.abs(np.diff(gray, axis=1, prepend=gray[:, :1]))
        gy = np.abs(np.diff(gray, axis=0, prepend=gray[:1, :]))
        grad = gx + gy
        total = float(np.sum(grad) + 1e-6)

        window = 16
        h, w = grad.shape
        max_share = 0.0
        for row in range(0, h - window + 1, max(1, window // 2)):
            for col in range(0, w - window + 1, max(1, window // 2)):
                region = grad[row : row + window, col : col + window]
                share = float(np.sum(region) / total)
                if share > max_share:
                    max_share = share
        return max_share
