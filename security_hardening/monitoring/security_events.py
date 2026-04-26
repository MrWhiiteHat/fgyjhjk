"""Structured security event schema and emission utilities."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


@dataclass
class SecurityEvent:
    """Canonical security event payload."""

    event_id: str
    timestamp: str
    category: str
    severity: str
    source: str
    message: str
    tenant_id: str | None = None
    user_id: str | None = None
    ip: str | None = None
    metadata: dict[str, str | float | int | bool] = field(default_factory=dict)


class SecurityEventEmitter:
    """Builds and serializes security events with consistent structure."""

    def emit(
        self,
        *,
        event_id: str,
        category: str,
        severity: str,
        source: str,
        message: str,
        tenant_id: str | None = None,
        user_id: str | None = None,
        ip: str | None = None,
        metadata: dict[str, str | float | int | bool] | None = None,
        timestamp: str | None = None,
    ) -> SecurityEvent:
        """Create structured security event object."""

        ts = timestamp or datetime.now(tz=timezone.utc).isoformat()
        return SecurityEvent(
            event_id=str(event_id),
            timestamp=str(ts),
            category=str(category),
            severity=str(severity),
            source=str(source),
            message=str(message),
            tenant_id=tenant_id,
            user_id=user_id,
            ip=ip,
            metadata=dict(metadata or {}),
        )

    @staticmethod
    def to_json(event: SecurityEvent) -> str:
        """Serialize event as compact JSON string."""

        return json.dumps(asdict(event), separators=(",", ":"), sort_keys=True)
