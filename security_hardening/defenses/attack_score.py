"""Unified normalized attack score combining multiple defense signals."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AttackScoreConfig:
    """Signal weighting policy for aggregate attack score."""

    weights: dict[str, float] = field(
        default_factory=lambda: {
            "input_guard": 0.25,
            "perturbation": 0.30,
            "uncertainty": 0.25,
            "query_pattern": 0.20,
        }
    )


@dataclass
class AttackScoreResult:
    """Aggregate attack score with severity and per-signal contribution."""

    score: float
    severity: str
    contributions: dict[str, float]


class AttackScorer:
    """Combines risk signals into a normalized severity score."""

    def __init__(self, config: AttackScoreConfig | None = None) -> None:
        self.config = config or AttackScoreConfig()

    def score(
        self,
        *,
        input_guard_decision: dict,
        perturbation_result: dict,
        uncertainty_decision: dict,
        query_pattern_result: dict,
    ) -> AttackScoreResult:
        """Calculate weighted risk score and severity tier."""

        input_component = self._input_guard_component(input_guard_decision)
        perturbation_component = float(perturbation_result.get("score", 0.0) or 0.0)
        uncertainty_component = float(uncertainty_decision.get("uncertainty_score", 0.0) or 0.0)
        query_component = float(query_pattern_result.get("risk_score", 0.0) or 0.0)

        components = {
            "input_guard": min(max(input_component, 0.0), 1.0),
            "perturbation": min(max(perturbation_component, 0.0), 1.0),
            "uncertainty": min(max(uncertainty_component, 0.0), 1.0),
            "query_pattern": min(max(query_component, 0.0), 1.0),
        }

        score = 0.0
        contributions: dict[str, float] = {}
        for key, value in components.items():
            weight = float(self.config.weights.get(key, 0.0))
            contribution = value * weight
            contributions[key] = contribution
            score += contribution
        score = min(max(score, 0.0), 1.0)

        if score >= 0.85:
            severity = "critical"
        elif score >= 0.65:
            severity = "high"
        elif score >= 0.35:
            severity = "medium"
        else:
            severity = "low"

        return AttackScoreResult(score=score, severity=severity, contributions=contributions)

    @staticmethod
    def _input_guard_component(decision: dict) -> float:
        """Map input guard action to normalized risk component."""

        action = str(decision.get("action", "allow")).lower().strip()
        if action == "block":
            return 1.0
        if action == "allow_with_warning":
            return 0.55
        return 0.0
