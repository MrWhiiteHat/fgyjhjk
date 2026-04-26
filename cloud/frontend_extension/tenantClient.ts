export type TenantRequestOptions = {
  tenantId: string;
  apiKey?: string;
  idempotencyKey?: string;
  principalId?: string;
};

export function buildTenantHeaders(options: TenantRequestOptions): Record<string, string> {
  const headers: Record<string, string> = {
    "X-Tenant-Id": options.tenantId,
  };

  if (options.apiKey) {
    headers["X-API-Key"] = options.apiKey;
  }
  if (options.idempotencyKey) {
    headers["Idempotency-Key"] = options.idempotencyKey;
  }
  if (options.principalId) {
    headers["X-Principal-Id"] = options.principalId;
  }

  return headers;
}

export async function tenantFetch<T>(
  url: string,
  options: TenantRequestOptions,
  init: RequestInit = {},
): Promise<T> {
  const tenantHeaders = buildTenantHeaders(options);
  const response = await fetch(url, {
    ...init,
    headers: {
      ...(init.headers ?? {}),
      ...tenantHeaders,
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    const payload = await response.text();
    throw new Error(`Tenant request failed (${response.status}): ${payload}`);
  }

  return (await response.json()) as T;
}

export function createIdempotencyKey(prefix = "idem"): string {
  const random = Math.random().toString(36).slice(2, 12);
  const timestamp = Date.now().toString(36);
  return `${prefix}_${timestamp}_${random}`;
}
