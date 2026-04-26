"""Tenant-scoped organization and workspace services."""

from __future__ import annotations

from dataclasses import replace
from threading import RLock
from typing import Dict, List

from cloud.platform.organizations.models import Invite, InviteStatus, MemberAssignment, Organization, Workspace
from cloud.platform.tenancy.guard import TenantGuard
from cloud.platform.utils.exceptions import NotFoundError, ValidationError
from cloud.platform.utils.ids import new_id
from cloud.platform.utils.time import utc_now_iso


_ALLOWED_SCOPE_TYPES = {"organization", "workspace"}


class OrganizationWorkspaceService:
    """CRUD and membership service with strict tenant boundaries."""

    def __init__(self) -> None:
        self._organizations: Dict[str, Organization] = {}
        self._workspaces: Dict[str, Workspace] = {}
        self._memberships: Dict[str, MemberAssignment] = {}
        self._invites: Dict[str, Invite] = {}
        self._lock = RLock()

    def create_organization(self, *, tenant_id: str, name: str, description: str = "") -> Organization:
        """Create tenant-scoped organization."""

        safe_name = str(name).strip()
        if not safe_name:
            raise ValidationError("Organization name is required")

        with self._lock:
            organization = Organization(
                organization_id=new_id("org"),
                tenant_id=str(tenant_id).strip(),
                name=safe_name,
                description=str(description).strip(),
            )
            self._organizations[organization.organization_id] = organization
            return organization

    def list_organizations(self, tenant_id: str) -> List[Organization]:
        """List organizations for tenant only."""

        return [org for org in self._organizations.values() if org.tenant_id == tenant_id]

    def get_organization(self, *, actor_tenant_id: str, organization_id: str) -> Organization:
        """Read organization with tenant isolation checks."""

        org = self._organizations.get(organization_id)
        if not org:
            raise NotFoundError(f"Organization not found: {organization_id}")
        TenantGuard.assert_same_tenant(actor_tenant_id, org.tenant_id)
        return org

    def update_organization(
        self,
        *,
        actor_tenant_id: str,
        organization_id: str,
        name: str | None = None,
        description: str | None = None,
    ) -> Organization:
        """Update organization fields under same tenant."""

        with self._lock:
            org = self.get_organization(actor_tenant_id=actor_tenant_id, organization_id=organization_id)
            updated = replace(
                org,
                name=str(name).strip() if name is not None else org.name,
                description=str(description).strip() if description is not None else org.description,
                updated_at=utc_now_iso(),
            )
            self._organizations[organization_id] = updated
            return updated

    def delete_organization(self, *, actor_tenant_id: str, organization_id: str) -> None:
        """Delete organization and all child workspaces under tenant guard."""

        with self._lock:
            org = self.get_organization(actor_tenant_id=actor_tenant_id, organization_id=organization_id)
            TenantGuard.assert_same_tenant(actor_tenant_id, org.tenant_id)

            to_delete = [wid for wid, ws in self._workspaces.items() if ws.organization_id == organization_id]
            for workspace_id in to_delete:
                del self._workspaces[workspace_id]

            del self._organizations[organization_id]

    def create_workspace(
        self,
        *,
        tenant_id: str,
        organization_id: str,
        name: str,
        description: str = "",
    ) -> Workspace:
        """Create workspace within organization under same tenant."""

        safe_name = str(name).strip()
        if not safe_name:
            raise ValidationError("Workspace name is required")

        with self._lock:
            org = self.get_organization(actor_tenant_id=tenant_id, organization_id=organization_id)
            workspace = Workspace(
                workspace_id=new_id("ws"),
                tenant_id=tenant_id,
                organization_id=org.organization_id,
                name=safe_name,
                description=str(description).strip(),
            )
            self._workspaces[workspace.workspace_id] = workspace
            return workspace

    def list_workspaces(self, *, actor_tenant_id: str, organization_id: str | None = None) -> List[Workspace]:
        """List workspaces for actor tenant, optionally filtered by organization."""

        output: List[Workspace] = []
        for workspace in self._workspaces.values():
            if workspace.tenant_id != actor_tenant_id:
                continue
            if organization_id and workspace.organization_id != organization_id:
                continue
            output.append(workspace)
        return output

    def get_workspace(self, *, actor_tenant_id: str, workspace_id: str) -> Workspace:
        """Read workspace with strict tenant isolation."""

        workspace = self._workspaces.get(workspace_id)
        if not workspace:
            raise NotFoundError(f"Workspace not found: {workspace_id}")
        TenantGuard.assert_same_tenant(actor_tenant_id, workspace.tenant_id)
        return workspace

    def update_workspace(
        self,
        *,
        actor_tenant_id: str,
        workspace_id: str,
        name: str | None = None,
        description: str | None = None,
    ) -> Workspace:
        """Update workspace under tenant checks."""

        with self._lock:
            workspace = self.get_workspace(actor_tenant_id=actor_tenant_id, workspace_id=workspace_id)
            updated = replace(
                workspace,
                name=str(name).strip() if name is not None else workspace.name,
                description=str(description).strip() if description is not None else workspace.description,
                updated_at=utc_now_iso(),
            )
            self._workspaces[workspace_id] = updated
            return updated

    def delete_workspace(self, *, actor_tenant_id: str, workspace_id: str) -> None:
        """Delete workspace in actor tenant."""

        with self._lock:
            workspace = self.get_workspace(actor_tenant_id=actor_tenant_id, workspace_id=workspace_id)
            TenantGuard.assert_same_tenant(actor_tenant_id, workspace.tenant_id)
            del self._workspaces[workspace_id]

    def add_member(
        self,
        *,
        actor_tenant_id: str,
        user_id: str,
        role: str,
        scope_type: str,
        scope_id: str,
    ) -> MemberAssignment:
        """Assign role to user at organization/workspace scope."""

        safe_scope = str(scope_type).strip().lower()
        if safe_scope not in _ALLOWED_SCOPE_TYPES:
            raise ValidationError(f"Unsupported scope_type: {scope_type}")
        if not str(user_id).strip():
            raise ValidationError("user_id is required")
        if not str(role).strip():
            raise ValidationError("role is required")

        self._validate_scope_belongs_to_tenant(actor_tenant_id=actor_tenant_id, scope_type=safe_scope, scope_id=scope_id)

        assignment = MemberAssignment(
            assignment_id=new_id("member"),
            tenant_id=actor_tenant_id,
            user_id=str(user_id).strip(),
            role=str(role).strip(),
            scope_type=safe_scope,
            scope_id=str(scope_id).strip(),
        )
        with self._lock:
            self._memberships[assignment.assignment_id] = assignment
        return assignment

    def list_members(self, *, actor_tenant_id: str, scope_type: str, scope_id: str) -> List[MemberAssignment]:
        """List members for scope in actor tenant."""

        safe_scope = str(scope_type).strip().lower()
        self._validate_scope_belongs_to_tenant(actor_tenant_id=actor_tenant_id, scope_type=safe_scope, scope_id=scope_id)
        return [
            member
            for member in self._memberships.values()
            if member.tenant_id == actor_tenant_id and member.scope_type == safe_scope and member.scope_id == scope_id
        ]

    def remove_member(self, *, actor_tenant_id: str, assignment_id: str) -> None:
        """Remove role assignment from tenant scope."""

        with self._lock:
            assignment = self._memberships.get(assignment_id)
            if not assignment:
                raise NotFoundError(f"Assignment not found: {assignment_id}")
            TenantGuard.assert_same_tenant(actor_tenant_id, assignment.tenant_id)
            del self._memberships[assignment_id]

    def create_invite(
        self,
        *,
        actor_tenant_id: str,
        email: str,
        role: str,
        scope_type: str,
        scope_id: str,
    ) -> Invite:
        """Create tenant-scoped invite for role onboarding."""

        safe_email = str(email).strip().lower()
        if "@" not in safe_email:
            raise ValidationError("Valid invite email is required")

        safe_scope = str(scope_type).strip().lower()
        self._validate_scope_belongs_to_tenant(actor_tenant_id=actor_tenant_id, scope_type=safe_scope, scope_id=scope_id)

        invite = Invite(
            invite_id=new_id("invite"),
            tenant_id=actor_tenant_id,
            email=safe_email,
            role=str(role).strip(),
            scope_type=safe_scope,
            scope_id=str(scope_id).strip(),
            invite_token=new_id("token"),
        )
        with self._lock:
            self._invites[invite.invite_id] = invite
        return invite

    def accept_invite(self, *, actor_tenant_id: str, invite_token: str, user_id: str) -> MemberAssignment:
        """Accept invite, create assignment, and mark invite accepted."""

        with self._lock:
            invite = self._find_invite_by_token(invite_token)
            TenantGuard.assert_same_tenant(actor_tenant_id, invite.tenant_id)
            if invite.status != InviteStatus.PENDING:
                raise ValidationError(f"Invite cannot be accepted from status: {invite.status}")

            member = self.add_member(
                actor_tenant_id=actor_tenant_id,
                user_id=user_id,
                role=invite.role,
                scope_type=invite.scope_type,
                scope_id=invite.scope_id,
            )
            self._invites[invite.invite_id] = replace(invite, status=InviteStatus.ACCEPTED, updated_at=utc_now_iso())
            return member

    def revoke_invite(self, *, actor_tenant_id: str, invite_id: str) -> Invite:
        """Revoke a pending invite in actor tenant."""

        with self._lock:
            invite = self._invites.get(invite_id)
            if not invite:
                raise NotFoundError(f"Invite not found: {invite_id}")
            TenantGuard.assert_same_tenant(actor_tenant_id, invite.tenant_id)
            updated = replace(invite, status=InviteStatus.REVOKED, updated_at=utc_now_iso())
            self._invites[invite_id] = updated
            return updated

    def _validate_scope_belongs_to_tenant(self, *, actor_tenant_id: str, scope_type: str, scope_id: str) -> None:
        if scope_type not in _ALLOWED_SCOPE_TYPES:
            raise ValidationError(f"Unsupported scope_type: {scope_type}")

        if scope_type == "organization":
            org = self.get_organization(actor_tenant_id=actor_tenant_id, organization_id=scope_id)
            TenantGuard.assert_same_tenant(actor_tenant_id, org.tenant_id)
            return

        workspace = self.get_workspace(actor_tenant_id=actor_tenant_id, workspace_id=scope_id)
        TenantGuard.assert_same_tenant(actor_tenant_id, workspace.tenant_id)

    def _find_invite_by_token(self, token: str) -> Invite:
        for invite in self._invites.values():
            if invite.invite_token == token:
                return invite
        raise NotFoundError("Invite token not found")
