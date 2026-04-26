"""Tenant CRUD service with isolation-safe access methods."""

from __future__ import annotations

from dataclasses import replace
from threading import RLock
from typing import Dict, List

from cloud.platform.config.plans import PlanTier
from cloud.platform.tenancy.guard import TenantGuard
from cloud.platform.tenancy.models import Tenant, TenantStatus
from cloud.platform.utils.exceptions import NotFoundError, ValidationError
from cloud.platform.utils.ids import new_id
from cloud.platform.utils.time import utc_now_iso


class TenantService:
    """In-memory tenant service for cloud control-plane operations."""

    def __init__(self) -> None:
        self._tenants: Dict[str, Tenant] = {}
        self._slug_to_tenant_id: Dict[str, str] = {}
        self._lock = RLock()

    def create_tenant(
        self,
        *,
        name: str,
        slug: str,
        plan_tier: PlanTier | str,
        deployment_mode: str = "shared_saas",
        metadata: dict[str, str] | None = None,
    ) -> Tenant:
        """Create a new tenant and reserve slug uniqueness."""

        safe_name = str(name).strip()
        safe_slug = str(slug).strip().lower()
        if not safe_name:
            raise ValidationError("Tenant name is required")
        if not safe_slug:
            raise ValidationError("Tenant slug is required")

        tier = plan_tier if isinstance(plan_tier, PlanTier) else PlanTier(str(plan_tier).strip().title())

        with self._lock:
            if safe_slug in self._slug_to_tenant_id:
                raise ValidationError(f"Tenant slug already exists: {safe_slug}")

            tenant = Tenant(
                tenant_id=new_id("tenant"),
                slug=safe_slug,
                name=safe_name,
                plan_tier=tier,
                deployment_mode=str(deployment_mode).strip() or "shared_saas",
                metadata=dict(metadata or {}),
            )
            self._tenants[tenant.tenant_id] = tenant
            self._slug_to_tenant_id[safe_slug] = tenant.tenant_id
            return tenant

    def get_tenant(self, tenant_id: str) -> Tenant:
        """Get tenant by ID."""

        with self._lock:
            tenant = self._tenants.get(tenant_id)
            if not tenant:
                raise NotFoundError(f"Tenant not found: {tenant_id}")
            return tenant

    def get_tenant_by_slug(self, slug: str) -> Tenant:
        """Get tenant by slug."""

        safe_slug = str(slug).strip().lower()
        with self._lock:
            tenant_id = self._slug_to_tenant_id.get(safe_slug)
            if not tenant_id:
                raise NotFoundError(f"Tenant not found for slug: {safe_slug}")
            return self.get_tenant(tenant_id)

    def list_tenants(self) -> List[Tenant]:
        """List all tenants."""

        with self._lock:
            return list(self._tenants.values())

    def update_tenant(
        self,
        tenant_id: str,
        *,
        name: str | None = None,
        plan_tier: PlanTier | str | None = None,
        deployment_mode: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> Tenant:
        """Update tenant metadata and mutable fields."""

        with self._lock:
            tenant = self.get_tenant(tenant_id)
            next_tier = tenant.plan_tier
            if plan_tier is not None:
                next_tier = plan_tier if isinstance(plan_tier, PlanTier) else PlanTier(str(plan_tier).strip().title())

            updated = replace(
                tenant,
                name=str(name).strip() if name is not None else tenant.name,
                plan_tier=next_tier,
                deployment_mode=(str(deployment_mode).strip() if deployment_mode is not None else tenant.deployment_mode),
                metadata=(dict(metadata) if metadata is not None else tenant.metadata),
                updated_at=utc_now_iso(),
            )
            self._tenants[tenant_id] = updated
            return updated

    def suspend_tenant(self, tenant_id: str) -> Tenant:
        """Suspend tenant operations."""

        return self._set_status(tenant_id, TenantStatus.SUSPENDED)

    def activate_tenant(self, tenant_id: str) -> Tenant:
        """Activate tenant operations."""

        return self._set_status(tenant_id, TenantStatus.ACTIVE)

    def delete_tenant(self, tenant_id: str) -> Tenant:
        """Soft-delete tenant and keep audit trail in memory."""

        return self._set_status(tenant_id, TenantStatus.DELETED)

    def assert_active(self, tenant_id: str) -> Tenant:
        """Require tenant to exist and be active."""

        tenant = self.get_tenant(tenant_id)
        if tenant.status != TenantStatus.ACTIVE:
            raise ValidationError(f"Tenant is not active: {tenant_id}")
        return tenant

    def assert_isolated_access(self, actor_tenant_id: str, resource_tenant_id: str) -> None:
        """Protect resource access with strict same-tenant validation."""

        TenantGuard.assert_same_tenant(actor_tenant_id=actor_tenant_id, resource_tenant_id=resource_tenant_id)

    def _set_status(self, tenant_id: str, status: TenantStatus) -> Tenant:
        with self._lock:
            tenant = self.get_tenant(tenant_id)
            updated = replace(tenant, status=status, updated_at=utc_now_iso())
            self._tenants[tenant_id] = updated
            return updated
