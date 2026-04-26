"""Tenant API key management service."""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from threading import RLock

from cloud.platform.tenancy.guard import TenantGuard
from cloud.platform.utils.exceptions import NotFoundError
from cloud.platform.utils.ids import new_id
from cloud.platform.utils.security import constant_time_equal, hmac_sha256
from cloud.platform.utils.time import utc_now_iso


@dataclass
class ApiKeyRecord:
    """Stored API key metadata with hashed secret."""

    key_id: str
    tenant_id: str
    name: str
    key_prefix: str
    key_hash: str
    active: bool = True
    created_at: str = field(default_factory=utc_now_iso)


class ApiKeyService:
    """Create, validate, and revoke tenant API keys."""

    def __init__(self, signing_secret: str) -> None:
        self._signing_secret = str(signing_secret)
        self._records: dict[str, ApiKeyRecord] = {}
        self._lock = RLock()

    def create_key(self, *, actor_tenant_id: str, tenant_id: str, name: str) -> tuple[ApiKeyRecord, str]:
        """Create API key for tenant and return raw key once."""

        TenantGuard.assert_same_tenant(actor_tenant_id, tenant_id)
        raw_secret = secrets.token_urlsafe(32)
        key_prefix = f"pk_{tenant_id[:8]}"
        raw_key = f"{key_prefix}.{raw_secret}"
        key_hash = hmac_sha256(self._signing_secret, raw_key)

        record = ApiKeyRecord(
            key_id=new_id("apikey"),
            tenant_id=tenant_id,
            name=str(name).strip() or "default",
            key_prefix=key_prefix,
            key_hash=key_hash,
        )
        with self._lock:
            self._records[record.key_id] = record
        return record, raw_key

    def revoke_key(self, *, actor_tenant_id: str, key_id: str) -> ApiKeyRecord:
        """Revoke existing API key."""

        with self._lock:
            record = self._records.get(key_id)
            if not record:
                raise NotFoundError(f"API key not found: {key_id}")
            TenantGuard.assert_same_tenant(actor_tenant_id, record.tenant_id)
            record.active = False
            self._records[key_id] = record
            return record

    def resolve_tenant(self, api_key: str) -> str | None:
        """Resolve tenant ID from raw API key when valid and active."""

        safe_key = str(api_key).strip()
        if not safe_key:
            return None

        expected_hash = hmac_sha256(self._signing_secret, safe_key)
        with self._lock:
            for record in self._records.values():
                if not record.active:
                    continue
                if constant_time_equal(record.key_hash, expected_hash):
                    return record.tenant_id
        return None

    def list_keys(self, *, actor_tenant_id: str, tenant_id: str) -> list[ApiKeyRecord]:
        """List API keys for tenant."""

        TenantGuard.assert_same_tenant(actor_tenant_id, tenant_id)
        with self._lock:
            return [record for record in self._records.values() if record.tenant_id == tenant_id]
