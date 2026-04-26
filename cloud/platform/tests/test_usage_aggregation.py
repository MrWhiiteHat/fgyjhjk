"""Usage aggregation tests for billing and reporting correctness."""

from __future__ import annotations

from cloud.platform.metering.service import MeteringService


def test_usage_aggregation_by_metric() -> None:
    metering = MeteringService()
    tenant_id = "tenant-usage"

    metering.record_usage(tenant_id=tenant_id, metric="image_inference", quantity=10)
    metering.record_usage(tenant_id=tenant_id, metric="image_inference", quantity=5)
    metering.record_usage(tenant_id=tenant_id, metric="video_inference", quantity=2)

    summary = metering.aggregate_usage(actor_tenant_id=tenant_id, tenant_id=tenant_id)

    assert summary.totals["image_inference"] == 15
    assert summary.totals["video_inference"] == 2


def test_usage_aggregation_excludes_other_tenants() -> None:
    metering = MeteringService()

    metering.record_usage(tenant_id="tenant-a", metric="image_inference", quantity=7)
    metering.record_usage(tenant_id="tenant-b", metric="image_inference", quantity=50)

    summary = metering.aggregate_usage(actor_tenant_id="tenant-a", tenant_id="tenant-a")

    assert summary.totals["image_inference"] == 7
