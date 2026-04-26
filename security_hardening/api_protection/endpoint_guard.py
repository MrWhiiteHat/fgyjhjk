"""Endpoint-level guard enforcing endpoint-specific protection rules."""

from __future__ import annotations

from dataclasses import dataclass, field

from security_hardening.api_protection.abuse_response import AbuseResponsePolicy


@dataclass
class EndpointGuardDecision:
    """Decision for a guarded endpoint invocation."""

    allowed: bool
    action: str
    reason_codes: list[str] = field(default_factory=list)
    metadata: dict[str, str | float] = field(default_factory=dict)


class EndpointGuard:
    """Evaluates endpoint policy with abuse score and tenant plan context."""

    ENDPOINT_POLICIES = {
        "/api/v1/predict/image": {"max_risk": 0.9, "allow_free_tier": True},
        "/api/v1/predict/video": {"max_risk": 0.8, "allow_free_tier": True},
        "/api/v1/predict/bulk": {"max_risk": 0.6, "allow_free_tier": False},
        "/api/v1/explain/image": {"max_risk": 0.5, "allow_free_tier": False},
    }

    def __init__(self, abuse_policy: AbuseResponsePolicy | None = None) -> None:
        self._abuse_policy = abuse_policy or AbuseResponsePolicy()

    def evaluate(
        self,
        *,
        endpoint: str,
        attack_risk_score: float,
        tenant_plan: str,
        repeated_offenses: int,
    ) -> EndpointGuardDecision:
        """Evaluate whether endpoint request should proceed or be constrained."""

        policy = self.ENDPOINT_POLICIES.get(endpoint, {"max_risk": 0.7, "allow_free_tier": True})
        max_risk = float(policy["max_risk"])
        free_allowed = bool(policy["allow_free_tier"])

        plan = str(tenant_plan).lower().strip()
        reasons: list[str] = []

        if plan == "free" and not free_allowed:
            reasons.append("endpoint_not_available_for_free_tier")

        if float(attack_risk_score) > max_risk:
            reasons.append("endpoint_risk_threshold_exceeded")

        abuse = self._abuse_policy.decide(
            risk_score=float(attack_risk_score),
            repeated_offenses=int(repeated_offenses),
            category="endpoint",
        )

        if abuse.action in {"block", "quarantine"}:
            reasons.append(f"abuse_policy_{abuse.action}")

        allowed = not reasons
        action = "allow" if allowed else abuse.action
        return EndpointGuardDecision(
            allowed=allowed,
            action=action,
            reason_codes=reasons if reasons else ["ok"],
            metadata={
                "endpoint": endpoint,
                "tenant_plan": plan,
                "risk_score": float(attack_risk_score),
            },
        )
