"""Report generation for usage, quota, and async jobs."""

from __future__ import annotations

from collections import Counter

from cloud.platform.config.plans import PlanTier, get_plan_definition
from cloud.platform.jobs.queue import AsyncJobQueue
from cloud.platform.metering.service import MeteringService
from cloud.platform.utils.time import utc_now_iso


class ReportingService:
    """Builds tenant-scoped operational reports."""

    def __init__(self, metering_service: MeteringService, job_queue: AsyncJobQueue) -> None:
        self._metering = metering_service
        self._job_queue = job_queue

    def usage_report(self, *, actor_tenant_id: str, tenant_id: str) -> dict:
        """Generate usage totals by metric."""

        usage = self._metering.aggregate_usage(actor_tenant_id=actor_tenant_id, tenant_id=tenant_id)
        return {
            "generated_at": utc_now_iso(),
            "tenant_id": tenant_id,
            "report_type": "usage",
            "totals": usage.totals,
        }

    def quota_report(self, *, actor_tenant_id: str, tenant_id: str, plan_tier: PlanTier | str) -> dict:
        """Generate quota status report from plan limits and current usage."""

        plan = get_plan_definition(plan_tier)
        usage = self._metering.aggregate_usage(actor_tenant_id=actor_tenant_id, tenant_id=tenant_id)

        quotas = {}
        for metric, hard_limit in plan.hard_limits.items():
            used = int(usage.totals.get(metric, 0))
            soft_limit = int(hard_limit * plan.soft_limit_ratio)
            quotas[metric] = {
                "used": used,
                "soft_limit": soft_limit,
                "hard_limit": hard_limit,
                "remaining": max(hard_limit - used, 0),
                "soft_warning": used >= soft_limit,
                "hard_block": used >= hard_limit,
            }

        return {
            "generated_at": utc_now_iso(),
            "tenant_id": tenant_id,
            "plan_tier": plan.tier.value,
            "report_type": "quota",
            "quotas": quotas,
        }

    def job_report(self, *, actor_tenant_id: str, tenant_id: str) -> dict:
        """Generate async job lifecycle report for tenant."""

        jobs = self._job_queue.list_jobs(actor_tenant_id=actor_tenant_id, tenant_id=tenant_id)
        status_counts = Counter(job.status.value for job in jobs)
        dead_letter_count = len(self._job_queue.list_dead_letter_jobs(actor_tenant_id=actor_tenant_id, tenant_id=tenant_id))

        return {
            "generated_at": utc_now_iso(),
            "tenant_id": tenant_id,
            "report_type": "jobs",
            "total_jobs": len(jobs),
            "status_counts": dict(status_counts),
            "dead_letter_count": dead_letter_count,
        }
