"""Billing-ready usage statement generation."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from cloud.platform.config.plans import PlanTier
from cloud.platform.utils.time import utc_now_iso

_PRICE_BOOK = {
    "image_inference": Decimal("0.0010"),
    "video_inference": Decimal("0.0200"),
    "explainability_usage": Decimal("0.0050"),
    "storage_usage": Decimal("0.00000002"),
    "async_jobs": Decimal("0.0008"),
}


def _discount_for_plan(plan_tier: PlanTier | str) -> Decimal:
    value = plan_tier.value if isinstance(plan_tier, PlanTier) else str(plan_tier)
    normalized = value.strip().lower()
    if normalized == "pro":
        return Decimal("0.05")
    if normalized == "team":
        return Decimal("0.10")
    if normalized == "enterprise":
        return Decimal("0.20")
    return Decimal("0.00")


def generate_usage_statement(
    *,
    tenant_id: str,
    plan_tier: PlanTier | str,
    usage_totals: dict[str, int],
    period_start: str,
    period_end: str,
) -> dict:
    """Generate billing-ready usage statement from metered totals."""

    line_items = []
    subtotal = Decimal("0")

    for metric, quantity in usage_totals.items():
        unit_price = _PRICE_BOOK.get(metric, Decimal("0"))
        qty = Decimal(str(int(quantity)))
        amount = qty * unit_price
        subtotal += amount
        line_items.append(
            {
                "metric": metric,
                "quantity": int(quantity),
                "unit_price": str(unit_price),
                "amount": str(amount.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
            }
        )

    discount_rate = _discount_for_plan(plan_tier)
    discount_amount = (subtotal * discount_rate).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    total = (subtotal - discount_amount).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    return {
        "generated_at": utc_now_iso(),
        "tenant_id": tenant_id,
        "plan_tier": plan_tier.value if isinstance(plan_tier, PlanTier) else str(plan_tier),
        "period_start": period_start,
        "period_end": period_end,
        "currency": "USD",
        "line_items": line_items,
        "subtotal": str(subtotal.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
        "discount_rate": str(discount_rate),
        "discount_amount": str(discount_amount),
        "estimated_total": str(total),
        "payment_integration": "not_included",
    }
