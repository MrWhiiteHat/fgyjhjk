"""Generate usage statement from sample metering data."""

from __future__ import annotations

from cloud.billing.usage_statement import generate_usage_statement


def main() -> None:
    statement = generate_usage_statement(
        tenant_id="tenant_demo_001",
        plan_tier="Team",
        usage_totals={
            "image_inference": 50000,
            "video_inference": 1500,
            "explainability_usage": 8000,
            "storage_usage": 1200000000,
            "async_jobs": 6500,
        },
        period_start="2026-04-01T00:00:00+00:00",
        period_end="2026-04-30T23:59:59+00:00",
    )
    print(statement)


if __name__ == "__main__":
    main()
