export type Role =
  | "platform_admin"
  | "tenant_admin"
  | "org_admin"
  | "workspace_admin"
  | "analyst"
  | "viewer";

export type Permission =
  | "tenant.manage"
  | "usage.read"
  | "jobs.manage"
  | "reports.export"
  | "org.manage"
  | "workspace.manage"
  | "members.invite"
  | "members.manage"
  | "api_keys.manage"
  | "gateway.invoke"
  | "billing.read"
  | "plan.manage"
  | "storage.manage"
  | "enterprise.manage";

const rolePermissions: Record<Role, Set<Permission>> = {
  platform_admin: new Set([
    "tenant.manage",
    "usage.read",
    "jobs.manage",
    "reports.export",
    "org.manage",
    "workspace.manage",
    "members.invite",
    "members.manage",
    "api_keys.manage",
    "gateway.invoke",
    "billing.read",
    "plan.manage",
    "storage.manage",
    "enterprise.manage",
  ]),
  tenant_admin: new Set([
    "tenant.manage",
    "usage.read",
    "jobs.manage",
    "reports.export",
    "org.manage",
    "workspace.manage",
    "members.invite",
    "members.manage",
    "api_keys.manage",
    "gateway.invoke",
    "billing.read",
    "plan.manage",
    "storage.manage",
  ]),
  org_admin: new Set([
    "usage.read",
    "jobs.manage",
    "reports.export",
    "org.manage",
    "workspace.manage",
    "members.invite",
    "members.manage",
    "gateway.invoke",
  ]),
  workspace_admin: new Set([
    "usage.read",
    "jobs.manage",
    "reports.export",
    "workspace.manage",
    "members.invite",
    "gateway.invoke",
  ]),
  analyst: new Set(["usage.read", "reports.export", "gateway.invoke"]),
  viewer: new Set(["usage.read", "gateway.invoke"]),
};

export function can(role: Role, permission: Permission): boolean {
  return rolePermissions[role].has(permission);
}
