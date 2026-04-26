"""Models for metering events and aggregation output."""

from __future__ import annotations

from dataclasses import dataclass, field

from cloud.platform.utils.time import utc_now_iso


@dataclass(frozen=True)
class UsageEvent:
    """Billable or reportable usage event."""

    event_id: str
    tenant_id: str
    metric: str
    quantity: int
    occurred_at: str = field(default_factory=utc_now_iso)
    workspace_id: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class UsageSummary:
    """Aggregated usage values by metric for a tenant."""

    tenant_id: str
    totals: dict[str, int]
    period_start: str | None = None
    period_end: str | None = None
