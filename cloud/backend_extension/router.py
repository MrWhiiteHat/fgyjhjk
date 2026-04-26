"""FastAPI router extension for cloud SaaS platform APIs."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from cloud.backend_extension.container import CloudPlatformContainer, get_cloud_container
from cloud.platform.authz.permissions import (
    API_KEYS_MANAGE,
    ENTERPRISE_MANAGE,
    JOBS_MANAGE,
    ORG_MANAGE,
    REPORTS_EXPORT,
    TENANT_MANAGE,
    USAGE_READ,
    WORKSPACE_MANAGE,
)
from cloud.platform.authz.roles import Role
from cloud.platform.config.plans import PlanTier
from cloud.platform.enterprise.models import DeploymentMode
from cloud.platform.enterprise.sso_scim import ScimProvisioningAdapter, SsoConfigurationAdapter
from cloud.platform.metering.models import UsageEvent
from cloud.platform.utils.exceptions import CloudPlatformError, QuotaExceededError

cloud_router = APIRouter(prefix="/api/v1/cloud", tags=["cloud"])


class AssignRoleRequest(BaseModel):
    principal_id: str
    role: Role
    tenant_id: str | None = None
    organization_id: str | None = None
    workspace_id: str | None = None


class TenantCreateRequest(BaseModel):
    name: str
    slug: str
    plan_tier: PlanTier = PlanTier.FREE
    deployment_mode: str = "shared_saas"
    metadata: dict[str, str] = Field(default_factory=dict)


class TenantUpdateRequest(BaseModel):
    name: str | None = None
    plan_tier: PlanTier | None = None
    deployment_mode: str | None = None
    metadata: dict[str, str] | None = None


class OrganizationCreateRequest(BaseModel):
    tenant_id: str
    name: str
    description: str = ""


class WorkspaceCreateRequest(BaseModel):
    tenant_id: str
    organization_id: str
    name: str
    description: str = ""


class UsageRecordRequest(BaseModel):
    tenant_id: str
    metric: str
    quantity: int = 1
    workspace_id: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class QuotaConsumeRequest(BaseModel):
    tenant_id: str
    metric: str
    quantity: int = 1
    workspace_id: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class EnqueueJobRequest(BaseModel):
    tenant_id: str
    job_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    max_retries: int = 3


class ApiKeyCreateRequest(BaseModel):
    tenant_id: str
    name: str


class EnterpriseModeRequest(BaseModel):
    tenant_id: str
    deployment_mode: DeploymentMode


class TenantResolveRequest(BaseModel):
    host: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)


def _principal_id(x_principal_id: str | None = Header(default=None, alias="X-Principal-Id")) -> str:
    if not x_principal_id or not str(x_principal_id).strip():
        raise HTTPException(status_code=401, detail="X-Principal-Id header is required")
    return str(x_principal_id).strip()


def _container() -> CloudPlatformContainer:
    return get_cloud_container()


def _require_permission(
    *,
    container: CloudPlatformContainer,
    principal_id: str,
    permission: str,
    tenant_id: str,
    organization_id: str | None = None,
    workspace_id: str | None = None,
) -> None:
    try:
        container.rbac_service.require_permission(
            principal_id=principal_id,
            permission=permission,
            tenant_id=tenant_id,
            organization_id=organization_id,
            workspace_id=workspace_id,
        )
    except CloudPlatformError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@cloud_router.post("/rbac/assign")
def assign_role(
    payload: AssignRoleRequest,
    container: CloudPlatformContainer = Depends(_container),
) -> dict:
    assignment = container.rbac_service.assign_role(
        principal_id=payload.principal_id,
        role=payload.role,
        tenant_id=payload.tenant_id,
        organization_id=payload.organization_id,
        workspace_id=payload.workspace_id,
    )
    return {"assignment": assignment.__dict__}


@cloud_router.post("/tenants")
def create_tenant(
    payload: TenantCreateRequest,
    principal_id: str = Depends(_principal_id),
    container: CloudPlatformContainer = Depends(_container),
) -> dict:
    _require_permission(
        container=container,
        principal_id=principal_id,
        permission=TENANT_MANAGE,
        tenant_id="platform_scope",
    )

    tenant = container.tenant_service.create_tenant(
        name=payload.name,
        slug=payload.slug,
        plan_tier=payload.plan_tier,
        deployment_mode=payload.deployment_mode,
        metadata=payload.metadata,
    )
    return {"tenant": tenant.__dict__}


@cloud_router.patch("/tenants/{tenant_id}")
def update_tenant(
    tenant_id: str,
    payload: TenantUpdateRequest,
    principal_id: str = Depends(_principal_id),
    container: CloudPlatformContainer = Depends(_container),
) -> dict:
    _require_permission(container=container, principal_id=principal_id, permission=TENANT_MANAGE, tenant_id=tenant_id)
    updated = container.tenant_service.update_tenant(
        tenant_id,
        name=payload.name,
        plan_tier=payload.plan_tier,
        deployment_mode=payload.deployment_mode,
        metadata=payload.metadata,
    )
    return {"tenant": updated.__dict__}


@cloud_router.post("/organizations")
def create_organization(
    payload: OrganizationCreateRequest,
    principal_id: str = Depends(_principal_id),
    container: CloudPlatformContainer = Depends(_container),
) -> dict:
    _require_permission(container=container, principal_id=principal_id, permission=ORG_MANAGE, tenant_id=payload.tenant_id)
    organization = container.organization_service.create_organization(
        tenant_id=payload.tenant_id,
        name=payload.name,
        description=payload.description,
    )
    return {"organization": organization.__dict__}


@cloud_router.post("/workspaces")
def create_workspace(
    payload: WorkspaceCreateRequest,
    principal_id: str = Depends(_principal_id),
    container: CloudPlatformContainer = Depends(_container),
) -> dict:
    _require_permission(
        container=container,
        principal_id=principal_id,
        permission=WORKSPACE_MANAGE,
        tenant_id=payload.tenant_id,
        organization_id=payload.organization_id,
    )
    workspace = container.organization_service.create_workspace(
        tenant_id=payload.tenant_id,
        organization_id=payload.organization_id,
        name=payload.name,
        description=payload.description,
    )
    return {"workspace": workspace.__dict__}


@cloud_router.post("/metering/record")
def record_usage(
    payload: UsageRecordRequest,
    principal_id: str = Depends(_principal_id),
    container: CloudPlatformContainer = Depends(_container),
) -> dict:
    _require_permission(container=container, principal_id=principal_id, permission=USAGE_READ, tenant_id=payload.tenant_id)
    event: UsageEvent = container.metering_service.record_usage(
        tenant_id=payload.tenant_id,
        metric=payload.metric,
        quantity=payload.quantity,
        workspace_id=payload.workspace_id,
        metadata=payload.metadata,
    )
    return {"event": event.__dict__}


@cloud_router.post("/quota/enforce")
def enforce_quota(
    payload: QuotaConsumeRequest,
    principal_id: str = Depends(_principal_id),
    container: CloudPlatformContainer = Depends(_container),
) -> dict:
    _require_permission(container=container, principal_id=principal_id, permission=USAGE_READ, tenant_id=payload.tenant_id)
    tenant = container.tenant_service.get_tenant(payload.tenant_id)
    try:
        decision = container.quota_service.enforce_and_record(
            actor_tenant_id=payload.tenant_id,
            tenant_id=payload.tenant_id,
            plan_tier=tenant.plan_tier,
            metric=payload.metric,
            requested_quantity=payload.quantity,
            workspace_id=payload.workspace_id,
            metadata=payload.metadata,
        )
    except QuotaExceededError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc

    return {"decision": decision.__dict__}


@cloud_router.post("/jobs")
def enqueue_job(
    payload: EnqueueJobRequest,
    principal_id: str = Depends(_principal_id),
    container: CloudPlatformContainer = Depends(_container),
) -> dict:
    _require_permission(container=container, principal_id=principal_id, permission=JOBS_MANAGE, tenant_id=payload.tenant_id)
    job = container.job_queue.enqueue(
        tenant_id=payload.tenant_id,
        job_type=payload.job_type,
        payload=payload.payload,
        max_retries=payload.max_retries,
    )
    return {"job": job.__dict__}


@cloud_router.get("/jobs/{tenant_id}/{job_id}")
def get_job(
    tenant_id: str,
    job_id: str,
    principal_id: str = Depends(_principal_id),
    container: CloudPlatformContainer = Depends(_container),
) -> dict:
    _require_permission(container=container, principal_id=principal_id, permission=USAGE_READ, tenant_id=tenant_id)
    job = container.job_queue.get_job(actor_tenant_id=tenant_id, job_id=job_id)
    return {"job": job.__dict__}


@cloud_router.get("/reports/usage/{tenant_id}")
def usage_report(
    tenant_id: str,
    principal_id: str = Depends(_principal_id),
    container: CloudPlatformContainer = Depends(_container),
) -> dict:
    _require_permission(container=container, principal_id=principal_id, permission=REPORTS_EXPORT, tenant_id=tenant_id)
    return container.reporting_service.usage_report(actor_tenant_id=tenant_id, tenant_id=tenant_id)


@cloud_router.get("/reports/quota/{tenant_id}")
def quota_report(
    tenant_id: str,
    principal_id: str = Depends(_principal_id),
    container: CloudPlatformContainer = Depends(_container),
) -> dict:
    _require_permission(container=container, principal_id=principal_id, permission=REPORTS_EXPORT, tenant_id=tenant_id)
    tenant = container.tenant_service.get_tenant(tenant_id)
    return container.reporting_service.quota_report(actor_tenant_id=tenant_id, tenant_id=tenant_id, plan_tier=tenant.plan_tier)


@cloud_router.get("/reports/jobs/{tenant_id}")
def jobs_report(
    tenant_id: str,
    principal_id: str = Depends(_principal_id),
    container: CloudPlatformContainer = Depends(_container),
) -> dict:
    _require_permission(container=container, principal_id=principal_id, permission=REPORTS_EXPORT, tenant_id=tenant_id)
    return container.reporting_service.job_report(actor_tenant_id=tenant_id, tenant_id=tenant_id)


@cloud_router.post("/api-keys")
def create_api_key(
    payload: ApiKeyCreateRequest,
    principal_id: str = Depends(_principal_id),
    container: CloudPlatformContainer = Depends(_container),
) -> dict:
    _require_permission(container=container, principal_id=principal_id, permission=API_KEYS_MANAGE, tenant_id=payload.tenant_id)
    record, raw_key = container.api_key_service.create_key(
        actor_tenant_id=payload.tenant_id,
        tenant_id=payload.tenant_id,
        name=payload.name,
    )
    return {"api_key": raw_key, "record": record.__dict__}


@cloud_router.post("/gateway/resolve")
def resolve_tenant(
    payload: TenantResolveRequest,
    container: CloudPlatformContainer = Depends(_container),
) -> dict:
    resolved = container.gateway_service.resolve_tenant(headers=payload.headers, host=payload.host)
    return {"tenant_id": resolved.tenant_id, "source": resolved.source}


@cloud_router.post("/enterprise/deployment-mode")
def set_enterprise_mode(
    payload: EnterpriseModeRequest,
    principal_id: str = Depends(_principal_id),
    container: CloudPlatformContainer = Depends(_container),
) -> dict:
    _require_permission(container=container, principal_id=principal_id, permission=ENTERPRISE_MANAGE, tenant_id=payload.tenant_id)
    tenant = container.tenant_service.get_tenant(payload.tenant_id)
    updated = container.enterprise_service.set_deployment_mode(
        actor_tenant_id=payload.tenant_id,
        tenant_id=payload.tenant_id,
        plan_tier=tenant.plan_tier,
        deployment_mode=payload.deployment_mode,
    )
    return {"profile": updated.__dict__}


@cloud_router.get("/enterprise/identity-status")
def identity_status() -> dict:
    return {
        "sso": SsoConfigurationAdapter.integration_status(),
        "scim": ScimProvisioningAdapter.integration_status(),
    }
