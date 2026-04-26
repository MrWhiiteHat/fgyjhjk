"""High-level API gateway orchestration helpers."""

from __future__ import annotations

import hashlib
import json
from typing import Callable

from cloud.platform.api_gateway.idempotency import IdempotencyService
from cloud.platform.api_gateway.tenant_resolution import TenantResolutionResult, TenantResolver


class ApiGatewayService:
    """Gateway service composing tenant resolution and idempotency controls."""

    def __init__(self, tenant_resolver: TenantResolver, idempotency_service: IdempotencyService) -> None:
        self._tenant_resolver = tenant_resolver
        self._idempotency = idempotency_service

    def resolve_tenant(self, *, headers: dict[str, str], host: str | None = None) -> TenantResolutionResult:
        """Resolve tenant for inbound request."""

        return self._tenant_resolver.resolve(headers=headers, host=host)

    def run_idempotent(
        self,
        *,
        tenant_id: str,
        idempotency_key: str,
        request_payload: dict,
        operation: Callable[[], dict],
    ) -> tuple[dict, bool]:
        """Run operation with idempotency replay support."""

        payload_hash = self._hash_payload(request_payload)
        replay = self._idempotency.check_or_replay(
            tenant_id=tenant_id,
            key=idempotency_key,
            request_hash=payload_hash,
        )
        if replay is not None:
            return replay, True

        response = operation()
        self._idempotency.store_response(
            tenant_id=tenant_id,
            key=idempotency_key,
            request_hash=payload_hash,
            response_payload=response,
        )
        return response, False

    @staticmethod
    def _hash_payload(payload: dict) -> str:
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
