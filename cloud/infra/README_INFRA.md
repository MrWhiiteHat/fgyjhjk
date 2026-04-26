# Cloud Infrastructure Notes

## Deployment Modes

- shared_saas: Multiple tenants in shared compute and storage planes with strict logical isolation.
- dedicated_tenant: Per-tenant isolated compute, network, and storage stack.

## Gateway Routing

Tenant resolution priority:

1. X-Tenant-Id header
2. API key mapping
3. Subdomain mapping

## Recommended Controls

- Enforce network segmentation for dedicated mode.
- Enable centralized audit logging.
- Use secret manager for signing secrets and API keys.
- Use object lifecycle rules for retention enforcement.
