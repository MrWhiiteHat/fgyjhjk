"""Organization and workspace domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from cloud.platform.utils.time import utc_now_iso


@dataclass
class Organization:
    """Tenant-scoped organization."""

    organization_id: str
    tenant_id: str
    name: str
    description: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)


@dataclass
class Workspace:
    """Tenant-scoped workspace owned by an organization."""

    workspace_id: str
    tenant_id: str
    organization_id: str
    name: str
    description: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)


@dataclass
class MemberAssignment:
    """Role assignment for user within organization or workspace."""

    assignment_id: str
    tenant_id: str
    user_id: str
    role: str
    scope_type: str
    scope_id: str
    created_at: str = field(default_factory=utc_now_iso)


class InviteStatus(str, Enum):
    """Invite lifecycle states."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    REVOKED = "revoked"
    EXPIRED = "expired"


@dataclass
class Invite:
    """Invite model for organization or workspace membership onboarding."""

    invite_id: str
    tenant_id: str
    email: str
    role: str
    scope_type: str
    scope_id: str
    invite_token: str
    status: InviteStatus = InviteStatus.PENDING
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
