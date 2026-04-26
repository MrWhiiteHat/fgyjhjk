"""Policy gate for secure explainability access."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ExplanationPolicyConfig:
    """Configuration for explainability access control."""

    enabled: bool = True
    max_risk_for_full_explanation: float = 0.45
    max_risk_for_any_explanation: float = 0.80
    allow_free_tier_full_explanation: bool = False


@dataclass
class ExplanationDecision:
    """Decision output for explanation access request."""

    allowed: bool
    mode: str
    reason_codes: list[str] = field(default_factory=list)


class ExplanationPolicy:
    """Determines explanation access and detail level based on risk and plan."""

    def __init__(self, config: ExplanationPolicyConfig | None = None) -> None:
        self.config = config or ExplanationPolicyConfig()

    def evaluate(self, *, risk_score: float, plan_tier: str | None, requested_mode: str) -> ExplanationDecision:
        """Evaluate whether explanation should be allowed and at what detail."""

        if not self.config.enabled:
            return ExplanationDecision(allowed=False, mode="none", reason_codes=["policy_disabled"])

        risk = float(min(max(risk_score, 0.0), 1.0))
        requested = str(requested_mode).lower().strip() or "standard"
        tier = str(plan_tier or "free").lower().strip()

        reasons: list[str] = []

        if risk >= self.config.max_risk_for_any_explanation:
            return ExplanationDecision(
                allowed=False,
                mode="none",
                reason_codes=["risk_too_high_for_explanation"],
            )

        if risk > self.config.max_risk_for_full_explanation and requested == "full":
            requested = "redacted"
            reasons.append("downgraded_due_to_risk")

        if tier == "free" and requested == "full" and not self.config.allow_free_tier_full_explanation:
            requested = "standard"
            reasons.append("free_tier_full_explanation_restricted")

        return ExplanationDecision(
            allowed=True,
            mode=requested,
            reason_codes=reasons if reasons else ["allowed"],
        )
