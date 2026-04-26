"""Plan tiers, feature flags, and quota defaults for SaaS tenants."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict

USAGE_IMAGE_INFERENCE = "image_inference"
USAGE_VIDEO_INFERENCE = "video_inference"
USAGE_EXPLAINABILITY = "explainability_usage"
USAGE_STORAGE_BYTES = "storage_usage"
USAGE_ASYNC_JOBS = "async_jobs"


class PlanTier(str, Enum):
    """Supported commercial plans."""

    FREE = "Free"
    PRO = "Pro"
    TEAM = "Team"
    ENTERPRISE = "Enterprise"


@dataclass(frozen=True)
class PlanDefinition:
    """Immutable plan configuration used for feature and quota checks."""

    tier: PlanTier
    hard_limits: Dict[str, int]
    soft_limit_ratio: float
    feature_flags: Dict[str, bool]


PLAN_CATALOG: Dict[PlanTier, PlanDefinition] = {
    PlanTier.FREE: PlanDefinition(
        tier=PlanTier.FREE,
        hard_limits={
            USAGE_IMAGE_INFERENCE: 1000,
            USAGE_VIDEO_INFERENCE: 100,
            USAGE_EXPLAINABILITY: 200,
            USAGE_STORAGE_BYTES: 5 * 1024 * 1024 * 1024,
            USAGE_ASYNC_JOBS: 100,
        },
        soft_limit_ratio=0.8,
        feature_flags={
            "priority_jobs": False,
            "advanced_reports": False,
            "dedicated_deployment": False,
            "sso": False,
            "scim": False,
        },
    ),
    PlanTier.PRO: PlanDefinition(
        tier=PlanTier.PRO,
        hard_limits={
            USAGE_IMAGE_INFERENCE: 25_000,
            USAGE_VIDEO_INFERENCE: 2_500,
            USAGE_EXPLAINABILITY: 5_000,
            USAGE_STORAGE_BYTES: 100 * 1024 * 1024 * 1024,
            USAGE_ASYNC_JOBS: 10_000,
        },
        soft_limit_ratio=0.85,
        feature_flags={
            "priority_jobs": True,
            "advanced_reports": True,
            "dedicated_deployment": False,
            "sso": False,
            "scim": False,
        },
    ),
    PlanTier.TEAM: PlanDefinition(
        tier=PlanTier.TEAM,
        hard_limits={
            USAGE_IMAGE_INFERENCE: 150_000,
            USAGE_VIDEO_INFERENCE: 15_000,
            USAGE_EXPLAINABILITY: 40_000,
            USAGE_STORAGE_BYTES: 500 * 1024 * 1024 * 1024,
            USAGE_ASYNC_JOBS: 120_000,
        },
        soft_limit_ratio=0.9,
        feature_flags={
            "priority_jobs": True,
            "advanced_reports": True,
            "dedicated_deployment": False,
            "sso": True,
            "scim": False,
        },
    ),
    PlanTier.ENTERPRISE: PlanDefinition(
        tier=PlanTier.ENTERPRISE,
        hard_limits={
            USAGE_IMAGE_INFERENCE: 2_000_000,
            USAGE_VIDEO_INFERENCE: 200_000,
            USAGE_EXPLAINABILITY: 400_000,
            USAGE_STORAGE_BYTES: 5 * 1024 * 1024 * 1024 * 1024,
            USAGE_ASYNC_JOBS: 1_000_000,
        },
        soft_limit_ratio=0.95,
        feature_flags={
            "priority_jobs": True,
            "advanced_reports": True,
            "dedicated_deployment": True,
            "sso": True,
            "scim": True,
        },
    ),
}


def get_plan_definition(plan_tier: PlanTier | str) -> PlanDefinition:
    """Resolve plan tier safely from enum or string value."""

    if isinstance(plan_tier, PlanTier):
        tier = plan_tier
    else:
        normalized = str(plan_tier).strip().lower()
        mapping = {item.value.lower(): item for item in PlanTier}
        if normalized not in mapping:
            raise ValueError(f"Unsupported plan tier: {plan_tier}")
        tier = mapping[normalized]

    return PLAN_CATALOG[tier]
