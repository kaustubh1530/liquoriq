"""
services/campaign_service.py — Campaign ROI tracking (Phase 12)

THE moat feature: proves whether a promotion actually moved product.

Method (derived on demand — no snapshots, no extra tables):
  baseline  = avg WEEKLY units/revenue of the promoted products in the
              28 days BEFORE the strategy was created
  campaign  = their weekly rate in the 14 days AFTER creation (or the
              elapsed part of it)
  lift      = campaign rate vs baseline rate, per product and in total

Why derive instead of snapshotting at creation?
  - normalized_sales keeps full dated history, so both windows are always
    computable — including for strategies created BEFORE this feature existed
    (retroactive, great for demos)
  - re-uploaded/corrected sales data automatically corrects the numbers
  - zero migrations

Honest limitations (say these in interviews):
  - correlation, not causation — no control group; a citywide heat wave can
    look like campaign lift
  - product matching is by exact (case-insensitive) name
  - baseline assumes the prior 4 weeks were "normal"
"""

import logging
import math
import uuid
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.ai_strategy_report import AIStrategyReport
from app.models.normalized_sale import NormalizedSale

logger = logging.getLogger(__name__)
settings = get_settings()


async def _window_totals(
    db: AsyncSession,
    store_id: uuid.UUID,
    names_lower: list[str],
    start: date,
    end: date,
) -> dict[str, dict]:
    """
    One grouped query: {product_name_lower: {"units": float, "revenue": float}}
    for sales with start <= sale_date < end.
    """
    result = await db.execute(
        select(
            func.lower(NormalizedSale.product_name).label("name"),
            func.coalesce(func.sum(NormalizedSale.quantity), 0).label("units"),
            func.coalesce(func.sum(NormalizedSale.total_amount), 0).label("revenue"),
        )
        .where(
            NormalizedSale.store_id == store_id,
            func.lower(NormalizedSale.product_name).in_(names_lower),
            NormalizedSale.sale_date >= start,
            NormalizedSale.sale_date < end,
        )
        .group_by(func.lower(NormalizedSale.product_name))
    )
    def _finite(v) -> float:
        f = float(v)
        return f if math.isfinite(f) else 0.0

    return {
        row.name: {"units": _finite(row.units), "revenue": _finite(row.revenue)}
        for row in result
    }


async def get_campaign_performance(
    strategy_id: uuid.UUID,
    store_id: uuid.UUID,
    db: AsyncSession,
) -> dict:
    """
    Full performance report for one strategy. Raises ValueError if the
    strategy doesn't exist / belong to this store.
    """
    result = await db.execute(
        select(AIStrategyReport).where(
            AIStrategyReport.id == strategy_id,
            AIStrategyReport.store_id == store_id,
        )
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise ValueError("Strategy not found")

    names = [str(n) for n in strategy.products_to_promote]
    names_lower = [n.lower() for n in names]

    campaign_start = strategy.created_at.date()
    campaign_end = campaign_start + timedelta(days=settings.campaign_window_days)
    baseline_start = campaign_start - timedelta(days=settings.baseline_window_days)
    today = date.today()

    # Elapsed measurable days inside the campaign window (min 1 on day one)
    measured_until = min(today, campaign_end)
    days_elapsed = max((measured_until - campaign_start).days + 1, 1)
    days_elapsed = min(days_elapsed, settings.campaign_window_days)

    baseline = await _window_totals(db, store_id, names_lower, baseline_start, campaign_start)
    # end bound is exclusive → +1 day so "today" counts
    campaign = await _window_totals(
        db, store_id, names_lower, campaign_start, measured_until + timedelta(days=1)
    )

    baseline_weeks = settings.baseline_window_days / 7
    campaign_weeks = days_elapsed / 7

    products = []
    tot_base_u = tot_base_r = tot_camp_u = tot_camp_r = 0.0
    for name, key in zip(names, names_lower):
        b = baseline.get(key, {"units": 0.0, "revenue": 0.0})
        c = campaign.get(key, {"units": 0.0, "revenue": 0.0})
        base_wu = b["units"] / baseline_weeks
        base_wr = b["revenue"] / baseline_weeks
        camp_wu = c["units"] / campaign_weeks
        camp_wr = c["revenue"] / campaign_weeks

        units_lift_pct = ((camp_wu - base_wu) / base_wu * 100) if base_wu > 0 else None
        # Extra revenue vs what baseline predicted for the elapsed period
        expected_rev = base_wr * campaign_weeks
        revenue_lift = c["revenue"] - expected_rev if b["revenue"] > 0 else None

        tot_base_u += base_wu
        tot_base_r += base_wr
        tot_camp_u += camp_wu
        tot_camp_r += camp_wr

        products.append({
            "product_name": name,
            "baseline_weekly_units": round(base_wu, 2),
            "baseline_weekly_revenue": round(base_wr, 2),
            "campaign_weekly_units": round(camp_wu, 2),
            "campaign_weekly_revenue": round(camp_wr, 2),
            "units_lift_pct": round(units_lift_pct, 1) if units_lift_pct is not None else None,
            "revenue_lift": round(revenue_lift, 2) if revenue_lift is not None else None,
        })

    has_baseline = tot_base_u > 0 or tot_base_r > 0
    if not has_baseline:
        status = "no_baseline"        # not enough history before the strategy
    elif today <= campaign_end:
        status = "measuring"
    else:
        status = "complete"

    total_units_lift_pct = (
        round((tot_camp_u - tot_base_u) / tot_base_u * 100, 1) if tot_base_u > 0 else None
    )
    total_revenue_lift = (
        round((tot_camp_r - tot_base_r) * campaign_weeks, 2) if tot_base_r > 0 else None
    )

    return {
        "strategy_id": strategy.id,
        "status": status,
        "campaign_start": campaign_start,
        "campaign_end": campaign_end,
        "days_elapsed": days_elapsed,
        "campaign_window_days": settings.campaign_window_days,
        "baseline_window_days": settings.baseline_window_days,
        "products": products,
        "total_units_lift_pct": total_units_lift_pct,
        "total_revenue_lift": total_revenue_lift,
    }
