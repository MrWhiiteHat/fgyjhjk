"""Quota checks and enforcement based on metered usage."""

from __future__ import annotations

from dataclasses import dataclass

from cloud.platform.config.plans import PlanTier, get_plan_definition
from cloud.platform.metering.service import MeteringService
from cloud.platform.utils.exceptions import QuotaExceededError, ValidationError


@dataclass(frozen=True)
class QuotaDecision:
    """Result of quota evaluation for a single operation."""

    allowed: bool
    warning: bool
    metric: str
    used: int
    requested: int
    hard_limit: int
    soft_limit: int
    remaining: int
    message: str


class QuotaService:
    """Hard and soft quota enforcement backed by metering totals."""

    def __init__(self, metering_service: MeteringService) -> None:
        self._metering = metering_service

    def evaluate(
        self,
        *,
        actor_tenant_id: str,
        tenant_id: str,
        plan_tier: PlanTier | str,
        metric: str,
        requested_quantity: int = 1,
    ) -> QuotaDecision:
        """Evaluate quota for upcoming operation without recording usage."""

        requested = int(requested_quantity)
        if requested <= 0:
            raise ValidationError("requested_quantity must be > 0")

        plan = get_plan_definition(plan_tier)
        hard_limit = int(plan.hard_limits.get(metric, 0))
        if hard_limit <= 0:
            raise ValidationError(f"Metric not configured for plan quotas: {metric}")

        used = self._metering.current_total(actor_tenant_id=actor_tenant_id, tenant_id=tenant_id, metric=metric)
        soft_limit = int(hard_limit * plan.soft_limit_ratio)
        projected = used + requested

        if projected > hard_limit:
            return QuotaDecision(
                allowed=False,
                warning=True,
                metric=metric,
                used=used,
                requested=requested,
                hard_limit=hard_limit,
                soft_limit=soft_limit,
                remaining=max(hard_limit - used, 0),
                message=f"Hard quota exceeded for metric={metric}: used={used}, requested={requested}, limit={hard_limit}",
            )

        warning = projected >= soft_limit
        remaining = hard_limit - projected
        message = "Within quota limits"
        if warning:
            message = (
                f"Soft quota warning for metric={metric}: projected={projected}, "
                f"soft_limit={soft_limit}, hard_limit={hard_limit}"
            )

        return QuotaDecision(
            allowed=True,
            warning=warning,
            metric=metric,
            used=used,
            requested=requested,
            hard_limit=hard_limit,
            soft_limit=soft_limit,
            remaining=remaining,
            message=message,
        )

    def enforce_and_record(
        self,
        *,
        actor_tenant_id: str,
        tenant_id: str,
        plan_tier: PlanTier | str,
        metric: str,
        requested_quantity: int = 1,
        workspace_id: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> QuotaDecision:
        """Enforce quota and record usage for allowed operations."""

        decision = self.evaluate(
            actor_tenant_id=actor_tenant_id,
            tenant_id=tenant_id,
            plan_tier=plan_tier,
            metric=metric,
            requested_quantity=requested_quantity,
        )
        if not decision.allowed:
            raise QuotaExceededError(decision.message)

        self._metering.record_usage(
            tenant_id=tenant_id,
            metric=metric,
            quantity=int(requested_quantity),
            workspace_id=workspace_id,
            metadata=metadata,
        )
        return decision
