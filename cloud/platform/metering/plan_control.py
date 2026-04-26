"""Feature gating helpers based on subscribed plan tiers."""

from __future__ import annotations

from cloud.platform.config.plans import PlanTier, get_plan_definition


class PlanControlService:
    """Evaluates feature availability for a tenant plan."""

    @staticmethod
    def has_feature(plan_tier: PlanTier | str, feature_name: str) -> bool:
        """Return whether feature is enabled under the selected plan."""

        plan = get_plan_definition(plan_tier)
        return bool(plan.feature_flags.get(str(feature_name).strip(), False))

    @staticmethod
    def list_features(plan_tier: PlanTier | str) -> dict[str, bool]:
        """Return feature flags for given plan."""

        return dict(get_plan_definition(plan_tier).feature_flags)
