"""Enterprise tier models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from cloud.platform.utils.time import utc_now_iso


class DeploymentMode(str, Enum):
    """Supported deployment topologies."""

    SHARED_SAAS = "shared_saas"
    DEDICATED_TENANT = "dedicated_tenant"


@dataclass
class EnterpriseProfile:
    """Enterprise configuration for a tenant."""

    tenant_id: str
    deployment_mode: DeploymentMode = DeploymentMode.SHARED_SAAS
    sso_enabled: bool = False
    scim_enabled: bool = False
    metadata: dict[str, str] = field(default_factory=dict)
    updated_at: str = field(default_factory=utc_now_iso)
