"""Usage event recording and aggregation logic."""

from __future__ import annotations

from datetime import datetime
from threading import RLock
from typing import List

from cloud.platform.metering.models import UsageEvent, UsageSummary
from cloud.platform.tenancy.guard import TenantGuard
from cloud.platform.utils.exceptions import ValidationError
from cloud.platform.utils.ids import new_id


class MeteringService:
    """In-memory event store for usage metering."""

    def __init__(self) -> None:
        self._events: List[UsageEvent] = []
        self._lock = RLock()

    def record_usage(
        self,
        *,
        tenant_id: str,
        metric: str,
        quantity: int = 1,
        workspace_id: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> UsageEvent:
        """Record a usage event for tenant-scoped billing and quota checks."""

        if not str(tenant_id).strip():
            raise ValidationError("tenant_id is required")
        if not str(metric).strip():
            raise ValidationError("metric is required")
        if int(quantity) <= 0:
            raise ValidationError("quantity must be > 0")

        event = UsageEvent(
            event_id=new_id("usage"),
            tenant_id=str(tenant_id).strip(),
            metric=str(metric).strip(),
            quantity=int(quantity),
            workspace_id=str(workspace_id).strip() if workspace_id else None,
            metadata=dict(metadata or {}),
        )
        with self._lock:
            self._events.append(event)
        return event

    def list_events(
        self,
        *,
        actor_tenant_id: str,
        tenant_id: str,
        metric: str | None = None,
    ) -> List[UsageEvent]:
        """List tenant usage events while enforcing tenant isolation."""

        TenantGuard.assert_same_tenant(actor_tenant_id, tenant_id)
        events = [event for event in self._events if event.tenant_id == tenant_id]
        if metric:
            safe_metric = str(metric).strip()
            events = [event for event in events if event.metric == safe_metric]
        return events

    def aggregate_usage(
        self,
        *,
        actor_tenant_id: str,
        tenant_id: str,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
    ) -> UsageSummary:
        """Aggregate usage totals by metric for a tenant and period."""

        TenantGuard.assert_same_tenant(actor_tenant_id, tenant_id)
        totals: dict[str, int] = {}
        for event in self._events:
            if event.tenant_id != tenant_id:
                continue

            event_dt = datetime.fromisoformat(event.occurred_at)
            if period_start and event_dt < period_start:
                continue
            if period_end and event_dt > period_end:
                continue
            totals[event.metric] = totals.get(event.metric, 0) + event.quantity

        return UsageSummary(
            tenant_id=tenant_id,
            totals=totals,
            period_start=period_start.isoformat() if period_start else None,
            period_end=period_end.isoformat() if period_end else None,
        )

    def current_total(self, *, actor_tenant_id: str, tenant_id: str, metric: str) -> int:
        """Get current cumulative usage for a metric in tenant scope."""

        events = self.list_events(actor_tenant_id=actor_tenant_id, tenant_id=tenant_id, metric=metric)
        return sum(item.quantity for item in events)
