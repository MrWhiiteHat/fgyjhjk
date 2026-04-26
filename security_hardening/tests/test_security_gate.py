from __future__ import annotations

from security_hardening.rollout.security_gate import SecurityGate


def test_security_gate_blocks_multiple_failures() -> None:
    gate = SecurityGate()

    decision = gate.evaluate(
        model_version="1.0.1",
        robustness_passed=False,
        robustness_degradation=0.25,
        artifact_integrity_passed=False,
        blocklisted_versions={"1.0.1"},
        extraction_risk_score=0.8,
        extraction_risk_threshold=0.5,
        poisoning_controls_configured=False,
    )

    assert decision.passed is False
    assert "robustness_tests_failed" in decision.reasons
    assert "artifact_verification_failed" in decision.reasons
    assert "model_version_blocklisted" in decision.reasons
    assert "extraction_risk_policy_not_satisfied" in decision.reasons
    assert "poisoning_controls_not_configured" in decision.reasons


def test_security_gate_passes_on_valid_candidate() -> None:
    gate = SecurityGate()

    decision = gate.evaluate(
        model_version="1.2.0",
        robustness_passed=True,
        robustness_degradation=0.05,
        artifact_integrity_passed=True,
        blocklisted_versions={"0.9.0"},
        extraction_risk_score=0.2,
        extraction_risk_threshold=0.5,
        poisoning_controls_configured=True,
    )

    assert decision.passed is True
    assert decision.reasons == ["passed"]
