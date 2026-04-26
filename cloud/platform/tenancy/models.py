"""Tenant domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict

from cloud.platform.config.plans import PlanTier
from cloud.platform.utils.time import utc_now_iso


class TenantStatus(str, Enum):
    """Tenant lifecycle states."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


@dataclass
class Tenant:
    """Tenant object used for request and storage partitioning."""

    tenant_id: str
    slug: str
    name: str
    plan_tier: PlanTier
    deployment_mode: str
    status: TenantStatus = TenantStatus.ACTIVE
    metadata: Dict[str, str] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
