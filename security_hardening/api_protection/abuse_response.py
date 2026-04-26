"""Abuse response policy engine for throttle/block/quarantine/alert actions."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AbuseResponseDecision:
    """Action plan derived from security abuse signals."""

    action: str
    reason_codes: list[str] = field(default_factory=list)
    should_alert: bool = False
    metadata: dict[str, float | str] = field(default_factory=dict)


class AbuseResponsePolicy:
    """Maps risk score and repeated offenses to response actions."""

    def decide(
        self,
        *,
        risk_score: float,
        repeated_offenses: int,
        category: str,
    ) -> AbuseResponseDecision:
        """Return throttle, block, quarantine, or alert decision."""

        risk = float(min(max(risk_score, 0.0), 1.0))
        offenses = int(max(repeated_offenses, 0))
        category_name = str(category).strip().lower()

        if risk >= 0.9 or offenses >= 6:
            action = "block"
            alert = True
        elif risk >= 0.75 or offenses >= 4:
            action = "quarantine"
            alert = True
        elif risk >= 0.45 or offenses >= 2:
            action = "throttle"
            alert = category_name in {"extraction", "poisoning", "artifact"}
        else:
            action = "allow"
            alert = False

        reasons = [f"risk_{risk:.2f}", f"offenses_{offenses}", f"category_{category_name}"]
        return AbuseResponseDecision(
            action=action,
            reason_codes=reasons,
            should_alert=alert,
            metadata={"risk_score": risk, "repeated_offenses": offenses, "category": category_name},
        )
