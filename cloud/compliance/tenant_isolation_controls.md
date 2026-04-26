# Tenant Isolation Controls

- Every service operation requires explicit tenant_id.
- No default tenant fallback is allowed.
- Cross-tenant operations are blocked by TenantGuard assertions.
- Storage paths are rooted under tenant-specific directories.
- Job lookup and reporting APIs are tenant-scoped.
- Metering records are tenant-scoped and filtered.
