"""Idempotency key storage and replay logic."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock

from cloud.platform.tenancy.guard import TenantGuard
from cloud.platform.utils.exceptions import IdempotencyConflictError
from cloud.platform.utils.time import utc_now


@dataclass
class IdempotencyRecord:
    """Stored idempotency response and payload fingerprint."""

    tenant_id: str
    key: str
    request_hash: str
    response_payload: dict
    expires_at_epoch: int


class IdempotencyService:
    """Stores idempotent responses per tenant and request hash."""

    def __init__(self, ttl_seconds: int = 24 * 60 * 60) -> None:
        self._ttl_seconds = int(ttl_seconds)
        self._records: dict[tuple[str, str], IdempotencyRecord] = {}
        self._lock = RLock()

    def check_or_replay(self, *, tenant_id: str, key: str, request_hash: str) -> dict | None:
        """Return cached response for matching request or raise on hash conflict."""

        cache_key = (str(tenant_id).strip(), str(key).strip())
        self._cleanup_expired()
        with self._lock:
            record = self._records.get(cache_key)
            if record is None:
                return None
            TenantGuard.assert_same_tenant(tenant_id, record.tenant_id)
            if record.request_hash != request_hash:
                raise IdempotencyConflictError("Idempotency key reused with a different request payload")
            return dict(record.response_payload)

    def store_response(self, *, tenant_id: str, key: str, request_hash: str, response_payload: dict) -> None:
        """Persist response for future idempotent replay."""

        cache_key = (str(tenant_id).strip(), str(key).strip())
        expires_at = int(utc_now().timestamp()) + self._ttl_seconds
        record = IdempotencyRecord(
            tenant_id=tenant_id,
            key=key,
            request_hash=request_hash,
            response_payload=dict(response_payload),
            expires_at_epoch=expires_at,
        )
        with self._lock:
            self._records[cache_key] = record

    def _cleanup_expired(self) -> None:
        now_epoch = int(utc_now().timestamp())
        with self._lock:
            expired = [key for key, value in self._records.items() if value.expires_at_epoch < now_epoch]
            for key in expired:
                del self._records[key]
