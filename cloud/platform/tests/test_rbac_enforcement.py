"""RBAC enforcement tests for cloud platform roles and permissions."""

from __future__ import annotations

import pytest

from cloud.platform.authz.permissions import JOBS_MANAGE, TENANT_MANAGE, USAGE_READ
from cloud.platform.authz.roles import Role
from cloud.platform.authz.service import RbacService
from cloud.platform.utils.exceptions import AuthorizationError


def test_tenant_admin_has_manage_permissions() -> None:
    rbac = RbacService()
    rbac.assign_role(principal_id="u-1", role=Role.TENANT_ADMIN, tenant_id="tenant-a")

    assert rbac.has_permission(principal_id="u-1", permission=TENANT_MANAGE, tenant_id="tenant-a") is True
    assert rbac.has_permission(principal_id="u-1", permission=USAGE_READ, tenant_id="tenant-a") is True


def test_viewer_cannot_manage_jobs() -> None:
    rbac = RbacService()
    rbac.assign_role(principal_id="u-2", role=Role.VIEWER, tenant_id="tenant-b")

    assert rbac.has_permission(principal_id="u-2", permission=JOBS_MANAGE, tenant_id="tenant-b") is False

    with pytest.raises(AuthorizationError):
        rbac.require_permission(principal_id="u-2", permission=JOBS_MANAGE, tenant_id="tenant-b")


def test_platform_admin_can_access_any_tenant_scope() -> None:
    rbac = RbacService()
    rbac.assign_role(principal_id="platform-root", role=Role.PLATFORM_ADMIN)

    assert rbac.has_permission(principal_id="platform-root", permission=TENANT_MANAGE, tenant_id="tenant-1") is True
    assert rbac.has_permission(principal_id="platform-root", permission=TENANT_MANAGE, tenant_id="tenant-2") is True
