"""RBAC assignment and authorization enforcement service."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Dict, List

from cloud.platform.authz.permissions import ALL_PERMISSIONS
from cloud.platform.authz.roles import ROLE_PERMISSION_MAP, Role
from cloud.platform.utils.exceptions import AuthorizationError, ValidationError
from cloud.platform.utils.ids import new_id


@dataclass
class RoleAssignment:
    """Role assignment at platform, tenant, org, or workspace scope."""

    assignment_id: str
    principal_id: str
    role: Role
    tenant_id: str | None = None
    organization_id: str | None = None
    workspace_id: str | None = None


class RbacService:
    """RBAC engine with hierarchical scope-aware permission resolution."""

    def __init__(self) -> None:
        self._assignments: Dict[str, RoleAssignment] = {}
        self._lock = RLock()

    def assign_role(
        self,
        *,
        principal_id: str,
        role: Role | str,
        tenant_id: str | None = None,
        organization_id: str | None = None,
        workspace_id: str | None = None,
    ) -> RoleAssignment:
        """Assign role at specific scope."""

        if not str(principal_id).strip():
            raise ValidationError("principal_id is required")

        role_enum = role if isinstance(role, Role) else Role(str(role).strip().lower())
        if role_enum != Role.PLATFORM_ADMIN and not str(tenant_id or "").strip():
            raise ValidationError("tenant_id is required for non-platform roles")

        assignment = RoleAssignment(
            assignment_id=new_id("rbac"),
            principal_id=str(principal_id).strip(),
            role=role_enum,
            tenant_id=str(tenant_id).strip() if tenant_id else None,
            organization_id=str(organization_id).strip() if organization_id else None,
            workspace_id=str(workspace_id).strip() if workspace_id else None,
        )
        with self._lock:
            self._assignments[assignment.assignment_id] = assignment
        return assignment

    def revoke_role(self, assignment_id: str) -> None:
        """Remove role assignment."""

        with self._lock:
            if assignment_id in self._assignments:
                del self._assignments[assignment_id]

    def list_assignments(self, principal_id: str | None = None) -> List[RoleAssignment]:
        """List role assignments optionally filtered by principal."""

        if principal_id is None:
            return list(self._assignments.values())
        safe_principal = str(principal_id).strip()
        return [item for item in self._assignments.values() if item.principal_id == safe_principal]

    def get_permissions(
        self,
        *,
        principal_id: str,
        tenant_id: str,
        organization_id: str | None = None,
        workspace_id: str | None = None,
    ) -> set[str]:
        """Resolve effective permissions for principal at target scope."""

        if not tenant_id:
            raise ValidationError("tenant_id is required")

        permissions: set[str] = set()
        for assignment in self.list_assignments(principal_id=principal_id):
            if assignment.role == Role.PLATFORM_ADMIN:
                permissions.update(ROLE_PERMISSION_MAP[Role.PLATFORM_ADMIN])
                continue

            if not assignment.tenant_id:
                continue

            if assignment.tenant_id != tenant_id:
                continue

            if assignment.workspace_id and workspace_id and assignment.workspace_id == workspace_id:
                permissions.update(ROLE_PERMISSION_MAP[assignment.role])
                continue

            if assignment.organization_id and organization_id and assignment.organization_id == organization_id:
                permissions.update(ROLE_PERMISSION_MAP[assignment.role])
                continue

            if assignment.tenant_id == tenant_id and not assignment.organization_id and not assignment.workspace_id:
                permissions.update(ROLE_PERMISSION_MAP[assignment.role])

        return permissions

    def has_permission(
        self,
        *,
        principal_id: str,
        permission: str,
        tenant_id: str,
        organization_id: str | None = None,
        workspace_id: str | None = None,
    ) -> bool:
        """Check if principal has given permission in scope."""

        safe_permission = str(permission).strip()
        if safe_permission not in ALL_PERMISSIONS:
            raise ValidationError(f"Unknown permission: {permission}")

        permissions = self.get_permissions(
            principal_id=principal_id,
            tenant_id=tenant_id,
            organization_id=organization_id,
            workspace_id=workspace_id,
        )
        return safe_permission in permissions

    def require_permission(
        self,
        *,
        principal_id: str,
        permission: str,
        tenant_id: str,
        organization_id: str | None = None,
        workspace_id: str | None = None,
    ) -> None:
        """Raise if principal lacks required permission."""

        if not self.has_permission(
            principal_id=principal_id,
            permission=permission,
            tenant_id=tenant_id,
            organization_id=organization_id,
            workspace_id=workspace_id,
        ):
            raise AuthorizationError(
                f"Permission denied for principal={principal_id}, permission={permission}, tenant={tenant_id}"
            )
