"""Regression test suite for candidate model behavior checks."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RegressionTestResult:
    """Outcome of regression test comparisons."""

    passed: bool
    failing_cases: int
    total_cases: int
    max_allowed_failure_rate: float


class RegressionTests:
    """Runs deterministic regression checks against production behavior."""

    def run(
        self,
        *,
        candidate_model,
        production_model,
        test_cases: list[dict],
        max_failure_rate: float = 0.05,
    ) -> RegressionTestResult:
        """Compare candidate predictions against production on critical cases."""

        if not test_cases:
            return RegressionTestResult(True, 0, 0, max_failure_rate)

        failing = 0
        for case in test_cases:
            features = dict(case.get("features") or {})
            production_pred = int(production_model.predict(features))
            candidate_pred = int(candidate_model.predict(features))

            expected = case.get("expected")
            if expected is not None:
                expected_pred = int(expected)
            else:
                expected_pred = production_pred

            if candidate_pred != expected_pred:
                failing += 1

        total = len(test_cases)
        failure_rate = failing / total
        passed = failure_rate <= float(max_failure_rate)
        return RegressionTestResult(
            passed=passed,
            failing_cases=failing,
            total_cases=total,
            max_allowed_failure_rate=float(max_failure_rate),
        )
