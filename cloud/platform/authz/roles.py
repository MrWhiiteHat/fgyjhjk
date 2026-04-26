"""RBAC role definitions and default permission grants."""

from __future__ import annotations

from enum import Enum

from cloud.platform.authz.permissions import (
    API_KEYS_MANAGE,
    BILLING_READ,
    ENTERPRISE_MANAGE,
    GATEWAY_INVOKE,
    JOBS_MANAGE,
    MEMBERS_INVITE,
    MEMBERS_MANAGE,
    ORG_MANAGE,
    PLAN_MANAGE,
    REPORTS_EXPORT,
    STORAGE_MANAGE,
    TENANT_MANAGE,
    USAGE_READ,
    WORKSPACE_MANAGE,
)


class Role(str, Enum):
    """Supported RBAC roles."""

    PLATFORM_ADMIN = "platform_admin"
    TENANT_ADMIN = "tenant_admin"
    ORG_ADMIN = "org_admin"
    WORKSPACE_ADMIN = "workspace_admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


ROLE_PERMISSION_MAP: dict[Role, set[str]] = {
    Role.PLATFORM_ADMIN: {
        TENANT_MANAGE,
        USAGE_READ,
        JOBS_MANAGE,
        REPORTS_EXPORT,
        ORG_MANAGE,
        WORKSPACE_MANAGE,
        MEMBERS_INVITE,
        MEMBERS_MANAGE,
        API_KEYS_MANAGE,
        GATEWAY_INVOKE,
        BILLING_READ,
        PLAN_MANAGE,
        STORAGE_MANAGE,
        ENTERPRISE_MANAGE,
    },
    Role.TENANT_ADMIN: {
        TENANT_MANAGE,
        USAGE_READ,
        JOBS_MANAGE,
        REPORTS_EXPORT,
        ORG_MANAGE,
        WORKSPACE_MANAGE,
        MEMBERS_INVITE,
        MEMBERS_MANAGE,
        API_KEYS_MANAGE,
        GATEWAY_INVOKE,
        BILLING_READ,
        PLAN_MANAGE,
        STORAGE_MANAGE,
    },
    Role.ORG_ADMIN: {
        USAGE_READ,
        JOBS_MANAGE,
        REPORTS_EXPORT,
        ORG_MANAGE,
        WORKSPACE_MANAGE,
        MEMBERS_INVITE,
        MEMBERS_MANAGE,
        GATEWAY_INVOKE,
    },
    Role.WORKSPACE_ADMIN: {
        USAGE_READ,
        JOBS_MANAGE,
        REPORTS_EXPORT,
        WORKSPACE_MANAGE,
        MEMBERS_INVITE,
        GATEWAY_INVOKE,
    },
    Role.ANALYST: {
        USAGE_READ,
        REPORTS_EXPORT,
        GATEWAY_INVOKE,
    },
    Role.VIEWER: {
        USAGE_READ,
        GATEWAY_INVOKE,
    },
}
