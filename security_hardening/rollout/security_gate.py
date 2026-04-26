"""Security release gate for blocking unsafe model rollout."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SecurityGateDecision:
    """Pass/fail decision and reasons for release gate."""

    passed: bool
    reasons: list[str] = field(default_factory=list)
    metrics: dict[str, float | bool | str] = field(default_factory=dict)


class SecurityGate:
    """Blocks release when mandatory security checks are not satisfied."""

    def evaluate(
        self,
        *,
        model_version: str,
        robustness_passed: bool,
        robustness_degradation: float,
        artifact_integrity_passed: bool,
        blocklisted_versions: set[str],
        extraction_risk_score: float,
        extraction_risk_threshold: float,
        poisoning_controls_configured: bool,
    ) -> SecurityGateDecision:
        """Evaluate release candidate against security gate criteria."""

        reasons: list[str] = []

        if not bool(robustness_passed):
            reasons.append("robustness_tests_failed")
        if not bool(artifact_integrity_passed):
            reasons.append("artifact_verification_failed")

        version = str(model_version).strip()
        if version in blocklisted_versions:
            reasons.append("model_version_blocklisted")

        if float(extraction_risk_score) > float(extraction_risk_threshold):
            reasons.append("extraction_risk_policy_not_satisfied")

        if not bool(poisoning_controls_configured):
            reasons.append("poisoning_controls_not_configured")

        return SecurityGateDecision(
            passed=not reasons,
            reasons=reasons if reasons else ["passed"],
            metrics={
                "model_version": version,
                "robustness_passed": bool(robustness_passed),
                "robustness_degradation": float(robustness_degradation),
                "artifact_integrity_passed": bool(artifact_integrity_passed),
                "extraction_risk_score": float(extraction_risk_score),
                "extraction_risk_threshold": float(extraction_risk_threshold),
                "poisoning_controls_configured": bool(poisoning_controls_configured),
            },
        )
