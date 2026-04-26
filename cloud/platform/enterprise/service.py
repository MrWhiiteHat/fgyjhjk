"""Enterprise profile service for deployment mode and identity settings."""

from __future__ import annotations

from dataclasses import replace
from threading import RLock

from cloud.platform.config.plans import PlanTier
from cloud.platform.enterprise.models import DeploymentMode, EnterpriseProfile
from cloud.platform.metering.plan_control import PlanControlService
from cloud.platform.tenancy.guard import TenantGuard
from cloud.platform.utils.time import utc_now_iso


class EnterpriseService:
    """Manages enterprise-only capabilities and deployment topology."""

    def __init__(self) -> None:
        self._profiles: dict[str, EnterpriseProfile] = {}
        self._lock = RLock()
        self._plan_control = PlanControlService()

    def get_profile(self, *, tenant_id: str) -> EnterpriseProfile:
        """Get enterprise profile, creating default if needed."""

        with self._lock:
            profile = self._profiles.get(tenant_id)
            if profile is None:
                profile = EnterpriseProfile(tenant_id=tenant_id)
                self._profiles[tenant_id] = profile
            return profile

    def set_deployment_mode(
        self,
        *,
        actor_tenant_id: str,
        tenant_id: str,
        plan_tier: PlanTier | str,
        deployment_mode: DeploymentMode | str,
    ) -> EnterpriseProfile:
        """Set deployment mode with plan-based capability checks."""

        TenantGuard.assert_same_tenant(actor_tenant_id, tenant_id)
        target_mode = (
            deployment_mode
            if isinstance(deployment_mode, DeploymentMode)
            else DeploymentMode(str(deployment_mode).strip().lower())
        )

        if target_mode == DeploymentMode.DEDICATED_TENANT and not self._plan_control.has_feature(plan_tier, "dedicated_deployment"):
            raise ValueError("Dedicated tenant deployment requires Enterprise plan capability")

        with self._lock:
            profile = self.get_profile(tenant_id=tenant_id)
            updated = replace(profile, deployment_mode=target_mode, updated_at=utc_now_iso())
            self._profiles[tenant_id] = updated
            return updated

    def configure_identity_features(
        self,
        *,
        actor_tenant_id: str,
        tenant_id: str,
        plan_tier: PlanTier | str,
        sso_enabled: bool,
        scim_enabled: bool,
    ) -> EnterpriseProfile:
        """Enable or disable SSO and SCIM flags based on plan features."""

        TenantGuard.assert_same_tenant(actor_tenant_id, tenant_id)

        if sso_enabled and not self._plan_control.has_feature(plan_tier, "sso"):
            raise ValueError("SSO is not available for this plan")
        if scim_enabled and not self._plan_control.has_feature(plan_tier, "scim"):
            raise ValueError("SCIM is not available for this plan")

        with self._lock:
            profile = self.get_profile(tenant_id=tenant_id)
            updated = replace(
                profile,
                sso_enabled=bool(sso_enabled),
                scim_enabled=bool(scim_enabled),
                updated_at=utc_now_iso(),
            )
            self._profiles[tenant_id] = updated
            return updated
