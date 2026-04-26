"""Quota enforcement tests for soft warnings and hard blocks."""

from __future__ import annotations

import pytest

from cloud.platform.config.plans import PlanTier, USAGE_IMAGE_INFERENCE
from cloud.platform.metering.quota import QuotaService
from cloud.platform.metering.service import MeteringService
from cloud.platform.utils.exceptions import QuotaExceededError


def test_soft_warning_before_hard_limit() -> None:
    metering = MeteringService()
    quota = QuotaService(metering)
    tenant_id = "tenant-soft"

    decision = quota.enforce_and_record(
        actor_tenant_id=tenant_id,
        tenant_id=tenant_id,
        plan_tier=PlanTier.FREE,
        metric=USAGE_IMAGE_INFERENCE,
        requested_quantity=850,
    )

    assert decision.allowed is True
    assert decision.warning is True


def test_hard_limit_blocks_usage() -> None:
    metering = MeteringService()
    quota = QuotaService(metering)
    tenant_id = "tenant-hard"

    quota.enforce_and_record(
        actor_tenant_id=tenant_id,
        tenant_id=tenant_id,
        plan_tier=PlanTier.FREE,
        metric=USAGE_IMAGE_INFERENCE,
        requested_quantity=1000,
    )

    with pytest.raises(QuotaExceededError):
        quota.enforce_and_record(
            actor_tenant_id=tenant_id,
            tenant_id=tenant_id,
            plan_tier=PlanTier.FREE,
            metric=USAGE_IMAGE_INFERENCE,
            requested_quantity=1,
        )
