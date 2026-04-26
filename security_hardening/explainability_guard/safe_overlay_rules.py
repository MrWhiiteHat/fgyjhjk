"""Safe overlay validation rules for explainability visualization."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class OverlayValidationResult:
    """Overlay validation outcome and adjustment actions."""

    allowed: bool
    reason_codes: list[str] = field(default_factory=list)
    normalized_params: dict[str, float] = field(default_factory=dict)


class SafeOverlayRules:
    """Validates overlay parameters to avoid unsafe or misleading display outputs."""

    def validate(
        self,
        *,
        width: int,
        height: int,
        alpha: float,
        max_side: int = 2048,
        min_side: int = 32,
    ) -> OverlayValidationResult:
        """Validate overlay dimensions and transparency constraints."""

        reasons: list[str] = []

        w = int(width)
        h = int(height)
        a = float(alpha)

        if w < min_side or h < min_side:
            reasons.append("overlay_too_small")
        if w > max_side or h > max_side:
            reasons.append("overlay_too_large")

        if a < 0.1:
            reasons.append("overlay_alpha_too_low")
        if a > 0.85:
            reasons.append("overlay_alpha_too_high")

        aspect = max(w / max(h, 1), h / max(w, 1)) if w and h else 0.0
        if aspect > 8.0:
            reasons.append("overlay_aspect_ratio_extreme")

        allowed = not reasons
        normalized = {
            "width": float(max(min(w, max_side), min_side)),
            "height": float(max(min(h, max_side), min_side)),
            "alpha": float(min(max(a, 0.15), 0.80)),
        }

        return OverlayValidationResult(
            allowed=allowed,
            reason_codes=reasons if reasons else ["overlay_safe"],
            normalized_params=normalized,
        )
