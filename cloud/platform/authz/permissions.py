"""Permission constants for SaaS control and data planes."""

from __future__ import annotations

TENANT_MANAGE = "tenant.manage"
USAGE_READ = "usage.read"
JOBS_MANAGE = "jobs.manage"
REPORTS_EXPORT = "reports.export"
ORG_MANAGE = "org.manage"
WORKSPACE_MANAGE = "workspace.manage"
MEMBERS_INVITE = "members.invite"
MEMBERS_MANAGE = "members.manage"
API_KEYS_MANAGE = "api_keys.manage"
GATEWAY_INVOKE = "gateway.invoke"
BILLING_READ = "billing.read"
PLAN_MANAGE = "plan.manage"
STORAGE_MANAGE = "storage.manage"
ENTERPRISE_MANAGE = "enterprise.manage"

ALL_PERMISSIONS = {
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
}
