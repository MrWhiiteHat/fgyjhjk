"""Validation rules for retraining datasets."""

from __future__ import annotations

import math
from dataclasses import dataclass

from ml_lifecycle.retraining.dataset_builder import TrainingSample


@dataclass
class ValidationResult:
    """Result of retraining dataset validation."""

    cleaned_samples: list[TrainingSample]
    dropped_samples: int
    class_distribution: dict[int, int]
    is_valid: bool
    reason: str


class DataValidation:
    """Removes corrupted samples and enforces class balance constraints."""

    def clean_and_validate(
        self,
        *,
        samples: list[TrainingSample],
        min_samples: int,
        min_class_ratio: float,
        max_class_ratio: float,
    ) -> ValidationResult:
        """Validate sample integrity and class balance requirements."""

        cleaned: list[TrainingSample] = []
        dropped = 0

        for sample in samples:
            if not sample.features:
                dropped += 1
                continue

            valid = True
            for value in sample.features.values():
                number = float(value)
                if math.isnan(number) or math.isinf(number):
                    valid = False
                    break
            if not valid:
                dropped += 1
                continue

            if int(sample.label) not in {0, 1}:
                dropped += 1
                continue

            cleaned.append(sample)

        distribution = {0: 0, 1: 0}
        for sample in cleaned:
            distribution[int(sample.label)] = distribution.get(int(sample.label), 0) + 1

        total = len(cleaned)
        if total < int(min_samples):
            return ValidationResult(
                cleaned_samples=cleaned,
                dropped_samples=dropped,
                class_distribution=distribution,
                is_valid=False,
                reason=f"Not enough samples after cleaning: {total} < {min_samples}",
            )

        major_ratio = max(distribution.values()) / total if total else 1.0
        minor_ratio = min(distribution.values()) / total if total else 0.0
        if minor_ratio < float(min_class_ratio) or major_ratio > float(max_class_ratio):
            return ValidationResult(
                cleaned_samples=cleaned,
                dropped_samples=dropped,
                class_distribution=distribution,
                is_valid=False,
                reason=(
                    "Class balance constraint failed: "
                    f"minor_ratio={minor_ratio:.4f}, major_ratio={major_ratio:.4f}"
                ),
            )

        return ValidationResult(
            cleaned_samples=cleaned,
            dropped_samples=dropped,
            class_distribution=distribution,
            is_valid=True,
            reason="ok",
        )
