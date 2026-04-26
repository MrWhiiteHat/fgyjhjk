from __future__ import annotations

import numpy as np

from security_hardening.defenses.perturbation_detector import PerturbationDetector, PerturbationDetectorConfig


def test_perturbation_detector_bounds_and_fields() -> None:
    detector = PerturbationDetector()
    image = np.full((64, 64, 3), 120, dtype=np.uint8)

    result = detector.detect(image)

    assert 0.0 <= result.score <= 1.0
    assert isinstance(result.reason_codes, list)
    assert isinstance(result.signals, dict)


def test_perturbation_detector_flags_patch_like_signal() -> None:
    detector = PerturbationDetector(config=PerturbationDetectorConfig(patch_threshold=0.05))
    image = np.full((96, 96, 3), 90, dtype=np.uint8)
    image[20:45, 20:45] = 255

    result = detector.detect(image)

    assert result.signals["localized_patch"] >= 0.0
    assert any(code in result.reason_codes for code in ["localized_patch_detected", "high_frequency_anomaly"])


def test_uncertainty_hint_mapping() -> None:
    detector = PerturbationDetector()
    image = np.full((64, 64, 3), 100, dtype=np.uint8)
    result = detector.detect(image)
    hint = detector.to_uncertainty_hint(result)

    assert 0.0 <= float(hint["perturbation_score"]) <= 1.0
    assert isinstance(hint["perturbation_suspicious"], bool)
