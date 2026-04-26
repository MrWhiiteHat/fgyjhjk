"""Bootstrap script for initializing cloud platform sample data."""

from __future__ import annotations

from cloud.backend_extension.container import CloudPlatformContainer
from cloud.platform.authz.roles import Role


def main() -> None:
    container = CloudPlatformContainer()
    container.start()

    tenant = container.tenant_service.create_tenant(
        name="Demo Tenant",
        slug="demo",
        plan_tier="Team",
        deployment_mode="shared_saas",
    )

    assignment = container.rbac_service.assign_role(
        principal_id="bootstrap-admin",
        role=Role.TENANT_ADMIN,
        tenant_id=tenant.tenant_id,
    )

    org = container.organization_service.create_organization(
        tenant_id=tenant.tenant_id,
        name="Demo Organization",
        description="Seeded organization",
    )

    ws = container.organization_service.create_workspace(
        tenant_id=tenant.tenant_id,
        organization_id=org.organization_id,
        name="Demo Workspace",
        description="Seeded workspace",
    )

    print("Cloud platform bootstrap complete")
    print({
        "tenant_id": tenant.tenant_id,
        "org_id": org.organization_id,
        "workspace_id": ws.workspace_id,
        "rbac_assignment": assignment.assignment_id,
    })

    container.stop()


if __name__ == "__main__":
    main()
