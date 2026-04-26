"""Optional ensemble-based second-opinion guard."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class EnsembleGuardConfig:
    """Ensemble operation policy and disagreement thresholds."""

    enabled: bool = False
    fallback_only: bool = True
    disagreement_threshold: float = 0.18
    require_review_on_disagreement: bool = True


@dataclass
class EnsembleDecision:
    """Decision payload for primary and backup model comparison."""

    enabled: bool
    used_backup: bool
    primary_probability: float
    backup_probability: float | None
    disagreement: float
    lowered_confidence: float
    flag_result: bool
    require_review: bool
    reason_codes: list[str] = field(default_factory=list)


class EnsembleGuard:
    """Compares primary and backup outputs and enforces conservative actions."""

    def __init__(self, config: EnsembleGuardConfig | None = None) -> None:
        self.config = config or EnsembleGuardConfig()

    def evaluate(
        self,
        *,
        primary_probability: float,
        backup_probability: float | None = None,
        backup_checker: Callable[[dict], float] | None = None,
        sample_features: dict | None = None,
    ) -> EnsembleDecision:
        """Evaluate disagreement and produce certainty-lowering guidance."""

        primary = float(min(max(primary_probability, 0.0), 1.0))

        if not self.config.enabled:
            return EnsembleDecision(
                enabled=False,
                used_backup=False,
                primary_probability=primary,
                backup_probability=None,
                disagreement=0.0,
                lowered_confidence=primary,
                flag_result=False,
                require_review=False,
                reason_codes=["ensemble_disabled"],
            )

        used_backup = False
        backup = backup_probability
        if backup is None and backup_checker is not None:
            backup = float(backup_checker(sample_features or {}))
            used_backup = True
        elif backup is not None:
            used_backup = True

        if backup is None:
            return EnsembleDecision(
                enabled=True,
                used_backup=False,
                primary_probability=primary,
                backup_probability=None,
                disagreement=0.0,
                lowered_confidence=primary,
                flag_result=False,
                require_review=False,
                reason_codes=["backup_unavailable"],
            )

        backup = float(min(max(backup, 0.0), 1.0))
        disagreement = abs(primary - backup)

        lowered = max(0.0, primary - 0.5 * disagreement)
        flag = disagreement >= self.config.disagreement_threshold
        require_review = bool(flag and self.config.require_review_on_disagreement)

        reasons = ["ensemble_enabled"]
        if flag:
            reasons.append("ensemble_disagreement_high")
        if self.config.fallback_only:
            reasons.append("fallback_only_mode")

        return EnsembleDecision(
            enabled=True,
            used_backup=used_backup,
            primary_probability=primary,
            backup_probability=backup,
            disagreement=disagreement,
            lowered_confidence=lowered,
            flag_result=flag,
            require_review=require_review,
            reason_codes=reasons,
        )
