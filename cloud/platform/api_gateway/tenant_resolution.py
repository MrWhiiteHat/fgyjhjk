"""Tenant resolution logic for gateway entry points."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from cloud.platform.api_gateway.api_keys import ApiKeyService
from cloud.platform.tenancy.service import TenantService
from cloud.platform.utils.exceptions import NotFoundError
from cloud.platform.utils.exceptions import ValidationError


@dataclass(frozen=True)
class TenantResolutionResult:
    """Result metadata from tenant resolution."""

    tenant_id: str
    source: str


class TenantResolver:
    """Resolves tenant from header, API key, or subdomain with strict priority."""

    def __init__(self, tenant_service: TenantService, api_key_service: ApiKeyService, tenant_header: str = "x-tenant-id") -> None:
        self._tenant_service = tenant_service
        self._api_key_service = api_key_service
        self._tenant_header = tenant_header.lower()

    def resolve(self, *, headers: dict[str, str], host: str | None = None) -> TenantResolutionResult:
        """Resolve tenant without fallback defaults."""

        normalized_headers = {str(k).lower(): str(v).strip() for k, v in headers.items()}

        header_tenant = normalized_headers.get(self._tenant_header)
        if header_tenant:
            tenant = self._tenant_service.get_tenant(header_tenant)
            return TenantResolutionResult(tenant_id=tenant.tenant_id, source="header")

        api_key = normalized_headers.get("x-api-key")
        auth_header = normalized_headers.get("authorization", "")
        if not api_key and auth_header.lower().startswith("bearer "):
            api_key = auth_header[7:].strip()

        if api_key:
            tenant_id = self._api_key_service.resolve_tenant(api_key)
            if not tenant_id:
                raise ValidationError("Invalid API key")
            return TenantResolutionResult(tenant_id=tenant_id, source="api_key")

        if host:
            tenant_id = self._resolve_from_subdomain(host)
            if tenant_id:
                return TenantResolutionResult(tenant_id=tenant_id, source="subdomain")

        raise ValidationError("Unable to resolve tenant. Provide x-tenant-id, API key, or mapped subdomain")

    def _resolve_from_subdomain(self, host: str) -> str | None:
        normalized = str(host).strip()
        if not normalized:
            return None

        if "://" in normalized:
            parsed = urlparse(normalized)
            hostname = parsed.hostname or ""
        else:
            hostname = normalized.split(":", 1)[0]

        labels = [label for label in hostname.split(".") if label]
        if len(labels) < 2:
            return None

        tenant_slug = labels[0].lower()
        try:
            tenant = self._tenant_service.get_tenant_by_slug(tenant_slug)
        except NotFoundError:
            return None
        return tenant.tenant_id
