"""Model policy enforcement for approved and blocklisted versions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ModelPolicyDecision:
    """Policy decision for model load or release action."""

    allowed: bool
    reason: str


class ModelPolicy:
    """Enforces approved-only and non-blocklisted model version rules."""

    def evaluate(
        self,
        *,
        model_version: str,
        approved_versions: set[str],
        blocklisted_versions: set[str],
        security_gate_passed: bool,
        strict_mode: bool = True,
    ) -> ModelPolicyDecision:
        """Evaluate policy for requested model version."""

        version = str(model_version).strip()
        if version in blocklisted_versions:
            return ModelPolicyDecision(allowed=False, reason="model_blocklisted")

        if strict_mode and version not in approved_versions:
            return ModelPolicyDecision(allowed=False, reason="model_not_approved")

        if strict_mode and not bool(security_gate_passed):
            return ModelPolicyDecision(allowed=False, reason="security_gate_not_passed")

        return ModelPolicyDecision(allowed=True, reason="ok")
