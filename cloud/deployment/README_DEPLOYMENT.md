# Cloud Deployment Guide

## Shared SaaS

Use the shared deployment mode for multi-tenant pooled infrastructure.

## Dedicated Tenant

Use dedicated deployment mode for enterprise tenants requiring isolated stacks.

## Startup Sequence

1. Apply migration assets.
2. Start backend extension with cloud router.
3. Ensure background job worker is running.
4. Seed initial RBAC platform_admin assignment.
