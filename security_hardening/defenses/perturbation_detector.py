"""Perturbation detector for common evasion-oriented image artifacts."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

try:
    import cv2  # type: ignore
except Exception:  # noqa: BLE001
    cv2 = None


@dataclass
class PerturbationDetectorConfig:
    """Detector thresholds and weighting for perturbation signals."""

    gaussian_noise_threshold: float = 20.0
    compression_artifact_threshold: float = 14.0
    high_frequency_threshold: float = 0.35
    patch_threshold: float = 0.40
    weights: dict[str, float] = field(
        default_factory=lambda: {
            "gaussian_noise": 0.30,
            "compression_artifact": 0.20,
            "high_frequency": 0.25,
            "localized_patch": 0.25,
        }
    )


@dataclass
class PerturbationResult:
    """Image-level perturbation risk result with interpretable metadata."""

    score: float
    suspicious: bool
    reason_codes: list[str]
    signals: dict[str, float]
    metadata: dict[str, str]


class PerturbationDetector:
    """Detects perturbation patterns tied to adversarial and evasion attempts."""

    def __init__(self, config: PerturbationDetectorConfig | None = None) -> None:
        self.config = config or PerturbationDetectorConfig()

    def detect(self, image: np.ndarray) -> PerturbationResult:
        """Run detector and return normalized perturbation score."""

        gray = self._to_gray(image)

        gaussian_noise = self._gaussian_noise_surge(gray)
        compression_artifact = self._compression_artifact_score(gray)
        high_frequency = self._high_frequency_anomaly(gray)
        localized_patch = self._localized_patch_score(gray)

        normalized = {
            "gaussian_noise": min(gaussian_noise / max(self.config.gaussian_noise_threshold, 1e-6), 2.0),
            "compression_artifact": min(
                compression_artifact / max(self.config.compression_artifact_threshold, 1e-6),
                2.0,
            ),
            "high_frequency": min(high_frequency / max(self.config.high_frequency_threshold, 1e-6), 2.0),
            "localized_patch": min(localized_patch / max(self.config.patch_threshold, 1e-6), 2.0),
        }

        score = 0.0
        for key, weight in self.config.weights.items():
            score += float(weight) * min(max(normalized.get(key, 0.0), 0.0), 1.0)
        score = min(max(score, 0.0), 1.0)

        reason_codes: list[str] = []
        if gaussian_noise >= self.config.gaussian_noise_threshold:
            reason_codes.append("gaussian_noise_surge")
        if compression_artifact >= self.config.compression_artifact_threshold:
            reason_codes.append("compression_artifacts_high")
        if high_frequency >= self.config.high_frequency_threshold:
            reason_codes.append("high_frequency_anomaly")
        if localized_patch >= self.config.patch_threshold:
            reason_codes.append("localized_patch_detected")

        return PerturbationResult(
            score=score,
            suspicious=bool(reason_codes),
            reason_codes=reason_codes,
            signals={
                "gaussian_noise": gaussian_noise,
                "compression_artifact": compression_artifact,
                "high_frequency": high_frequency,
                "localized_patch": localized_patch,
            },
            metadata={
                "detector": "perturbation_detector_v1",
                "note": "Heuristic perturbation detection with interpretable signals",
            },
        )

    @staticmethod
    def to_uncertainty_hint(result: PerturbationResult) -> dict[str, float | bool]:
        """Generate uncertainty-gate hint from perturbation result."""

        return {
            "perturbation_score": float(result.score),
            "perturbation_suspicious": bool(result.suspicious),
        }

    @staticmethod
    def _to_gray(image: np.ndarray) -> np.ndarray:
        """Convert image into grayscale float32 array."""

        arr = image.astype(np.float32)
        if arr.ndim == 2:
            return arr
        if arr.shape[2] == 1:
            return arr[:, :, 0]
        if cv2 is not None:
            return cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
        return np.mean(arr[:, :, :3], axis=2)

    @staticmethod
    def _gaussian_noise_surge(gray: np.ndarray) -> float:
        """Estimate additive noise level from denoising residual."""

        if cv2 is not None:
            den = cv2.GaussianBlur(gray, (5, 5), 0)
        else:
            den = gray
        residual = gray - den
        return float(np.std(residual))

    @staticmethod
    def _compression_artifact_score(gray: np.ndarray) -> float:
        """Measure JPEG-like block boundary discontinuities."""

        h, w = gray.shape
        if h < 16 or w < 16:
            return 0.0

        vertical_edges = []
        for col in range(8, w, 8):
            if col <= 0 or col >= w:
                continue
            jump = np.abs(gray[:, col - 1] - gray[:, col])
            vertical_edges.append(np.mean(jump))

        horizontal_edges = []
        for row in range(8, h, 8):
            if row <= 0 or row >= h:
                continue
            jump = np.abs(gray[row - 1, :] - gray[row, :])
            horizontal_edges.append(np.mean(jump))

        score = float(np.mean(vertical_edges + horizontal_edges)) if (vertical_edges or horizontal_edges) else 0.0
        return score

    @staticmethod
    def _high_frequency_anomaly(gray: np.ndarray) -> float:
        """Estimate high-frequency energy ratio from FFT magnitudes."""

        fft = np.fft.fftshift(np.fft.fft2(gray))
        magnitude = np.abs(fft)
        total = float(np.sum(magnitude) + 1e-6)

        h, w = gray.shape
        cy, cx = h // 2, w // 2
        radius = max(4, min(h, w) // 8)

        yy, xx = np.ogrid[:h, :w]
        mask = (yy - cy) ** 2 + (xx - cx) ** 2 >= radius**2
        high_energy = float(np.sum(magnitude[mask]))
        return high_energy / total

    @staticmethod
    def _localized_patch_score(gray: np.ndarray) -> float:
        """Estimate patch-like perturbation concentration by local variance peaks."""

        h, w = gray.shape
        if h < 16 or w < 16:
            return 0.0

        window = 16
        variances = []
        for row in range(0, h - window + 1, window // 2):
            for col in range(0, w - window + 1, window // 2):
                patch = gray[row : row + window, col : col + window]
                variances.append(float(np.var(patch)))

        if not variances:
            return 0.0
        variances_arr = np.array(variances, dtype=np.float32)
        baseline = float(np.mean(variances_arr) + 1e-6)
        peak = float(np.max(variances_arr))
        return peak / baseline / 10.0
