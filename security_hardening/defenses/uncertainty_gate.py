"""Uncertainty gate to prevent overconfident responses on risky samples."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class UncertaintyGateConfig:
    """Configuration thresholds for uncertainty decisioning."""

    decision_threshold: float = 0.5
    uncertainty_band: float = 0.08
    entropy_threshold: float = 0.85
    ensemble_disagreement_threshold: float = 0.18


@dataclass
class UncertaintyDecision:
    """Decision output from uncertainty gate."""

    action: str
    uncertainty_score: float
    reason_codes: list[str] = field(default_factory=list)
    metadata: dict[str, float | bool] = field(default_factory=dict)


class UncertaintyGate:
    """Computes uncertainty across threshold band, entropy, and ensemble disagreement."""

    def __init__(self, config: UncertaintyGateConfig | None = None) -> None:
        self.config = config or UncertaintyGateConfig()

    def evaluate(
        self,
        *,
        probability: float,
        probability_vector: list[float] | None = None,
        ensemble_disagreement: float | None = None,
        perturbation_hint: dict[str, float | bool] | None = None,
    ) -> UncertaintyDecision:
        """Evaluate uncertainty and return action policy."""

        p = float(min(max(probability, 0.0), 1.0))
        reasons: list[str] = []

        band_dist = abs(p - self.config.decision_threshold)
        band_signal = max(0.0, 1.0 - (band_dist / max(self.config.uncertainty_band, 1e-6)))
        if band_dist <= self.config.uncertainty_band:
            reasons.append("threshold_band_uncertainty")

        entropy_signal = 0.0
        if probability_vector:
            entropy_signal = self._normalized_entropy(probability_vector)
            if entropy_signal >= self.config.entropy_threshold:
                reasons.append("entropy_uncertainty")

        disagreement_signal = 0.0
        if ensemble_disagreement is not None:
            disagreement_signal = float(max(ensemble_disagreement, 0.0))
            if disagreement_signal >= self.config.ensemble_disagreement_threshold:
                reasons.append("ensemble_disagreement")

        perturbation_score = 0.0
        if perturbation_hint:
            perturbation_score = float(perturbation_hint.get("perturbation_score", 0.0) or 0.0)
            if bool(perturbation_hint.get("perturbation_suspicious", False)):
                reasons.append("perturbation_suspicion")

        uncertainty_score = min(
            1.0,
            0.35 * band_signal + 0.30 * entropy_signal + 0.20 * disagreement_signal + 0.15 * perturbation_score,
        )

        if uncertainty_score >= 0.75:
            action = "flag_for_review"
        elif uncertainty_score >= 0.45:
            action = "suppress_high_confidence_claim"
        else:
            action = "accept"

        return UncertaintyDecision(
            action=action,
            uncertainty_score=uncertainty_score,
            reason_codes=sorted(set(reasons)) if reasons else ["stable"],
            metadata={
                "band_distance": band_dist,
                "entropy_signal": entropy_signal,
                "ensemble_disagreement": disagreement_signal,
                "perturbation_score": perturbation_score,
            },
        )

    @staticmethod
    def _normalized_entropy(probabilities: list[float]) -> float:
        """Compute normalized Shannon entropy for probability vector."""

        probs = np.array(probabilities, dtype=np.float64)
        probs = np.clip(probs, 1e-12, 1.0)
        probs = probs / np.sum(probs)
        entropy = float(-np.sum(probs * np.log2(probs)))
        max_entropy = float(np.log2(len(probs))) if len(probs) > 1 else 1.0
        return min(max(entropy / max(max_entropy, 1e-12), 0.0), 1.0)
