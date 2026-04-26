"""Candidate model acceptance validation before production promotion."""

from __future__ import annotations

from dataclasses import dataclass, field

from ml_lifecycle.evaluation.bias_checks import BiasChecks, BiasCheckResult
from ml_lifecycle.evaluation.regression_tests import RegressionTestResult, RegressionTests


@dataclass
class ValidationResult:
    """Validation summary used to gate promotion and rollout."""

    passed: bool
    reasons: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)
    regression: RegressionTestResult | None = None
    bias: BiasCheckResult | None = None


class ModelValidator:
    """Validates candidate model against production and acceptance criteria."""

    def __init__(self, regression_tests: RegressionTests | None = None, bias_checks: BiasChecks | None = None) -> None:
        self._regression_tests = regression_tests or RegressionTests()
        self._bias_checks = bias_checks or BiasChecks()

    def validate(
        self,
        *,
        candidate_model,
        production_model,
        validation_samples: list[dict],
        regression_cases: list[dict],
        acceptance_criteria: dict,
        candidate_latency_ms: float,
        production_latency_ms: float,
    ) -> ValidationResult:
        """Run full validation and return acceptance decision."""

        reasons: list[str] = []

        candidate_accuracy, candidate_error = self._accuracy_and_error(candidate_model, validation_samples)
        production_accuracy, _ = self._accuracy_and_error(production_model, validation_samples)

        min_accuracy = float(acceptance_criteria.get("minimum_accuracy", 0.85))
        max_regression = float(acceptance_criteria.get("max_accuracy_regression", 0.01))
        max_error_rate = float(acceptance_criteria.get("max_error_rate", 0.15))
        max_latency = float(acceptance_criteria.get("max_latency_ms", 120.0))
        max_bias_increase = float(acceptance_criteria.get("max_bias_disparity_increase", 0.03))

        if candidate_accuracy < min_accuracy:
            reasons.append(f"Candidate accuracy below minimum threshold ({candidate_accuracy:.4f} < {min_accuracy:.4f})")

        if candidate_accuracy < (production_accuracy - max_regression):
            reasons.append(
                "Candidate model regressed beyond allowed margin "
                f"({candidate_accuracy:.4f} < {production_accuracy - max_regression:.4f})"
            )

        if candidate_error > max_error_rate:
            reasons.append(f"Candidate error rate exceeds threshold ({candidate_error:.4f} > {max_error_rate:.4f})")

        if candidate_latency_ms > max_latency:
            reasons.append(f"Candidate latency exceeds threshold ({candidate_latency_ms:.2f} > {max_latency:.2f})")

        if candidate_latency_ms > production_latency_ms + max_latency:
            reasons.append(
                "Candidate latency spike versus production exceeds acceptable bound "
                f"({candidate_latency_ms:.2f} > {production_latency_ms + max_latency:.2f})"
            )

        regression = self._regression_tests.run(
            candidate_model=candidate_model,
            production_model=production_model,
            test_cases=regression_cases,
            max_failure_rate=0.05,
        )
        if not regression.passed:
            reasons.append(
                "Regression tests failed "
                f"({regression.failing_cases}/{regression.total_cases} failures)"
            )

        bias = self._bias_checks.evaluate(
            candidate_model=candidate_model,
            production_model=production_model,
            samples=validation_samples,
            max_disparity_increase=max_bias_increase,
        )
        if not bias.passed:
            reasons.append(
                "Bias disparity increased beyond allowed threshold "
                f"({bias.disparity_increase:.4f} > {max_bias_increase:.4f})"
            )

        passed = not reasons
        return ValidationResult(
            passed=passed,
            reasons=reasons,
            metrics={
                "candidate_accuracy": candidate_accuracy,
                "production_accuracy": production_accuracy,
                "candidate_error_rate": candidate_error,
                "candidate_latency_ms": float(candidate_latency_ms),
                "production_latency_ms": float(production_latency_ms),
            },
            regression=regression,
            bias=bias,
        )

    @staticmethod
    def _accuracy_and_error(model, samples: list[dict]) -> tuple[float, float]:
        labeled = [sample for sample in samples if sample.get("label") is not None]
        if not labeled:
            return 0.0, 1.0

        correct = 0
        for sample in labeled:
            pred = int(model.predict(dict(sample.get("features") or {})))
            if pred == int(sample["label"]):
                correct += 1

        accuracy = correct / len(labeled)
        return accuracy, 1.0 - accuracy
