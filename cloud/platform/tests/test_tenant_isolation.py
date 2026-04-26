"""Tenant isolation tests for cloud platform services."""

from __future__ import annotations

import pytest

from cloud.platform.jobs.queue import AsyncJobQueue
from cloud.platform.metering.service import MeteringService
from cloud.platform.organizations.service import OrganizationWorkspaceService
from cloud.platform.tenancy.service import TenantService
from cloud.platform.utils.exceptions import TenantIsolationError


def test_organization_access_is_tenant_isolated() -> None:
    tenants = TenantService()
    orgs = OrganizationWorkspaceService()

    t1 = tenants.create_tenant(name="Tenant One", slug="tenant-one", plan_tier="Free")
    t2 = tenants.create_tenant(name="Tenant Two", slug="tenant-two", plan_tier="Free")

    org = orgs.create_organization(tenant_id=t1.tenant_id, name="Org 1")

    with pytest.raises(TenantIsolationError):
        orgs.get_organization(actor_tenant_id=t2.tenant_id, organization_id=org.organization_id)


def test_metering_access_is_tenant_isolated() -> None:
    tenants = TenantService()
    metering = MeteringService()

    t1 = tenants.create_tenant(name="Tenant One", slug="tenant-one-m", plan_tier="Free")
    t2 = tenants.create_tenant(name="Tenant Two", slug="tenant-two-m", plan_tier="Free")

    metering.record_usage(tenant_id=t1.tenant_id, metric="image_inference", quantity=1)

    with pytest.raises(TenantIsolationError):
        metering.list_events(actor_tenant_id=t2.tenant_id, tenant_id=t1.tenant_id)


def test_job_access_is_tenant_isolated() -> None:
    tenants = TenantService()
    queue = AsyncJobQueue()

    t1 = tenants.create_tenant(name="Tenant One", slug="tenant-one-j", plan_tier="Free")
    t2 = tenants.create_tenant(name="Tenant Two", slug="tenant-two-j", plan_tier="Free")

    job = queue.enqueue(tenant_id=t1.tenant_id, job_type="inference", payload={"input": "x"})

    with pytest.raises(TenantIsolationError):
        queue.get_job(actor_tenant_id=t2.tenant_id, job_id=job.job_id)
