"""Tenant isolation guardrails for strict access checks."""

from __future__ import annotations

from typing import Any, Callable, Iterable, List

from cloud.platform.tenancy.context import get_tenant_context
from cloud.platform.utils.exceptions import TenantIsolationError, ValidationError


class TenantGuard:
    """Guard methods that deny cross-tenant operations by default."""

    @staticmethod
    def assert_same_tenant(actor_tenant_id: str, resource_tenant_id: str) -> None:
        """Require actor and resource to belong to the same tenant."""

        if not actor_tenant_id or not resource_tenant_id:
            raise ValidationError("Both actor_tenant_id and resource_tenant_id are required")
        if actor_tenant_id != resource_tenant_id:
            raise TenantIsolationError(
                f"Cross-tenant access blocked: actor={actor_tenant_id}, resource={resource_tenant_id}"
            )

    @staticmethod
    def assert_context_tenant(resource_tenant_id: str) -> None:
        """Ensure current tenant context can access the resource tenant."""

        context_tenant = get_tenant_context(required=True)
        TenantGuard.assert_same_tenant(context_tenant, resource_tenant_id)

    @staticmethod
    def filter_for_tenant(
        resources: Iterable[Any], tenant_getter: Callable[[Any], str], tenant_id: str | None = None
    ) -> List[Any]:
        """Return resources scoped to a given tenant."""

        tenant = tenant_id or get_tenant_context(required=True)
        return [resource for resource in resources if tenant_getter(resource) == tenant]
