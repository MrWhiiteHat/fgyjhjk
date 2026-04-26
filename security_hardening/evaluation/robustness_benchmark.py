"""Robustness benchmark runner for candidate model security evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from security_hardening.evaluation.perturbation_suite import PerturbationSuite


@dataclass
class RobustnessBenchmarkResult:
    """Benchmark result with per-case metrics and pass/fail status."""

    passed: bool
    baseline_accuracy: float
    perturbed_accuracy: float
    degradation: float
    per_case_accuracy: dict[str, float] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)


class RobustnessBenchmark:
    """Runs perturbation suite and measures model performance degradation."""

    def __init__(self, suite: PerturbationSuite | None = None) -> None:
        self._suite = suite or PerturbationSuite()

    def run(
        self,
        *,
        model,
        samples: list[dict],
        max_allowed_degradation: float,
        min_perturbed_accuracy: float,
    ) -> RobustnessBenchmarkResult:
        """Evaluate robustness over perturbation suite against acceptance thresholds."""

        if not samples:
            return RobustnessBenchmarkResult(
                passed=False,
                baseline_accuracy=0.0,
                perturbed_accuracy=0.0,
                degradation=1.0,
                reasons=["no_samples"],
            )

        baseline_correct = 0
        total = 0

        per_case_totals: dict[str, int] = {}
        per_case_correct: dict[str, int] = {}

        for sample in samples:
            image = np.asarray(sample.get("image"), dtype=np.uint8)
            label = int(sample.get("label"))
            features = self._features_from_image(image)
            pred = int(model.predict(features))
            baseline_correct += int(pred == label)
            total += 1

            for case in self._suite.run(image):
                case_features = self._features_from_image(case.image)
                case_pred = int(model.predict(case_features))
                per_case_totals[case.name] = per_case_totals.get(case.name, 0) + 1
                per_case_correct[case.name] = per_case_correct.get(case.name, 0) + int(case_pred == label)

        baseline_accuracy = baseline_correct / max(total, 1)
        per_case_accuracy = {
            name: per_case_correct.get(name, 0) / max(per_case_totals.get(name, 1), 1)
            for name in sorted(per_case_totals.keys())
        }

        perturbed_accuracy = sum(per_case_accuracy.values()) / max(len(per_case_accuracy), 1)
        degradation = baseline_accuracy - perturbed_accuracy

        reasons: list[str] = []
        if degradation > float(max_allowed_degradation):
            reasons.append("degradation_exceeds_threshold")
        if perturbed_accuracy < float(min_perturbed_accuracy):
            reasons.append("perturbed_accuracy_below_threshold")

        return RobustnessBenchmarkResult(
            passed=not reasons,
            baseline_accuracy=baseline_accuracy,
            perturbed_accuracy=perturbed_accuracy,
            degradation=degradation,
            per_case_accuracy=per_case_accuracy,
            reasons=reasons if reasons else ["ok"],
        )

    @staticmethod
    def _features_from_image(image: np.ndarray) -> dict[str, float]:
        """Extract simple numeric features from image for model interface compatibility."""

        arr = image.astype(np.float32)
        mean = float(np.mean(arr) / 255.0)
        std = float(np.std(arr) / 255.0)
        edge = float(np.mean(np.abs(np.diff(arr, axis=0))) / 255.0)
        return {"x": mean + edge, "y": std}
