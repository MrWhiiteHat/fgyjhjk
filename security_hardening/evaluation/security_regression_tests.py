"""Security regression test runner for release candidates."""

from __future__ import annotations

from dataclasses import dataclass, field

from security_hardening.defenses.input_guard import InputGuard
from security_hardening.defenses.perturbation_detector import PerturbationDetector


@dataclass
class SecurityRegressionResult:
    """Security regression run summary."""

    passed: bool
    checks: dict[str, bool] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)


class SecurityRegressionTests:
    """Executes baseline security checks expected for each release."""

    def __init__(self, input_guard: InputGuard | None = None, perturbation_detector: PerturbationDetector | None = None) -> None:
        self._input_guard = input_guard or InputGuard()
        self._perturbation_detector = perturbation_detector or PerturbationDetector()

    def run(self, *, sample_image_bytes: bytes, sample_filename: str, sample_image_array) -> SecurityRegressionResult:
        """Run regression checks for malformed blocking and perturbation scoring."""

        checks: dict[str, bool] = {}
        reasons: list[str] = []

        decision = self._input_guard.evaluate(
            filename=sample_filename,
            payload=sample_image_bytes,
            claimed_mime="image/jpeg",
            source_key="regression",
        )
        checks["input_guard_non_block_for_valid_sample"] = decision.action in {"allow", "allow_with_warning"}
        if not checks["input_guard_non_block_for_valid_sample"]:
            reasons.append("input_guard_valid_sample_blocked")

        perturb = self._perturbation_detector.detect(sample_image_array)
        checks["perturbation_score_bounded"] = 0.0 <= perturb.score <= 1.0
        if not checks["perturbation_score_bounded"]:
            reasons.append("perturbation_score_out_of_bounds")

        return SecurityRegressionResult(
            passed=all(checks.values()),
            checks=checks,
            reasons=reasons if reasons else ["ok"],
        )
