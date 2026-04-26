# MODULE 8: CLOUD SCALING + MULTI-TENANT SAAS + ENTERPRISE LAYER

This module implements a full cloud SaaS control-plane extension with strict tenant isolation, RBAC, metering, quotas, async jobs, API gateway primitives, enterprise controls, and billing-ready outputs.

## 1. Folder structure

Implemented exactly under cloud/:

- platform/
  - config/
  - tenancy/
  - organizations/
  - authz/
  - metering/
  - jobs/
  - storage/
  - api_gateway/
  - enterprise/
  - reporting/
  - migrations/
  - utils/
  - tests/
- backend_extension/
- frontend_extension/
- infra/
- compliance/
- billing/
- deployment/
- scripts/

## 2. Config files

- Plan catalog with Free, Pro, Team, Enterprise limits and feature flags.
- Runtime cloud settings from environment variables.
- Default config file at platform/config/defaults.yaml.

## 3. Tenant system

- Tenant CRUD: create, update, suspend, activate, soft delete.
- Tenant context helpers for request propagation.
- TenantGuard enforces strict same-tenant checks.

## 4. Organization/workspace system

- Organization CRUD under tenant scope.
- Workspace CRUD under organization + tenant scope.
- Member assignment APIs and invite lifecycle (create, accept, revoke).

## 5. RBAC system

Roles:

- platform_admin
- tenant_admin
- org_admin
- workspace_admin
- analyst
- viewer

Permissions include:

- tenant.manage
- usage.read
- jobs.manage
- reports.export
- org.manage
- workspace.manage
- members.invite
- members.manage
- api_keys.manage
- gateway.invoke
- billing.read
- plan.manage
- storage.manage
- enterprise.manage

## 6. Metering + quota system

Metered metrics:

- image_inference
- video_inference
- explainability_usage
- storage_usage
- async_jobs

Quota enforcement:

- Soft warning threshold based on per-plan ratio.
- Hard block with QuotaExceededError.

## 7. Job system

- Thread-safe async queue.
- Background worker with handler registry.
- Retry logic by max_retries.
- Dead letter queue for exhausted failures.

## 8. Storage system

- Tenant-isolated storage roots.
- Signed URL generation + verification.
- Retention policy sweeper for max-age deletion.

## 9. API gateway

- Tenant resolution from:
  1) X-Tenant-Id header
  2) API key
  3) subdomain
- API key create/revoke/resolve.
- Idempotency key replay + conflict protection.
- Webhook signing and verification.

## 10. Enterprise features

Deployment modes:

- shared_saas
- dedicated_tenant

Identity features:

- SSO documented via integration status adapter.
- SCIM documented via integration status adapter.

## 11. Reporting

- Usage report generator.
- Quota report generator.
- Job lifecycle report generator.
- Example report outputs included under platform/reporting/example_outputs/.

## 12. Backend extension

FastAPI router extension under backend_extension/ exposing cloud APIs for:

- tenant operations
- RBAC assignment
- org/workspace operations
- metering + quota consume
- async jobs
- reports
- api keys
- gateway tenant resolution
- enterprise deployment mode

## 13. Frontend extension

TypeScript helper layer under frontend_extension/ for:

- tenant-aware request headers
- idempotency key generation
- role/permission checks
- plan feature flags
- quota UI status helpers

## 14. Infra docs

- Shared SaaS and dedicated tenant Kubernetes templates.
- Infrastructure guidance and routing model documentation.

## 15. Tests

Mandatory test coverage added under platform/tests/:

- tenant isolation
- RBAC enforcement
- quota enforcement
- usage aggregation
- job lifecycle

## 16. Example outputs

Provided examples:

- usage report
- quota report
- job report
- usage statement

All example payloads are in platform/reporting/example_outputs/.

## 17. Final validation

Cloud Platform Ready
--------------------
Multi-Tenant Enabled: Yes
Tenant Isolation: Yes
RBAC Working: Yes
Quota Enforcement: Yes
Usage Metering: Yes
Async Jobs: Yes
API Gateway: Yes
Enterprise Modes: Yes
Tests Passing: Yes
