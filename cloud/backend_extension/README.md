# Backend Extension

This extension exposes cloud SaaS endpoints at /api/v1/cloud using FastAPI.

## Include Router

Import cloud_router from cloud.backend_extension.router and include it in the main API app.

## Runtime

The extension initializes a service container with:

- Multi-tenant control plane services
- RBAC service
- Metering and quota enforcement
- Async job queue + worker
- API gateway primitives
- Enterprise mode controls
- Reporting endpoints
