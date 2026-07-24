"""
services/analytics_service.py — All analytics query logic for LiquorIQ

Every function here takes a store_id and an async db session, runs a
SQLAlchemy aggregate query against normalized_sales, and returns plain
Python dicts that the route layer converts to Pydantic response schemas.

Why keep queries here instead of in the route?
  - Routes handle HTTP concerns (auth, status codes, response shapes)
  - Services handle business logic (what data means, how to aggregate it)
  - This separation means you can call these functions from a background
    task, a scheduled report, or an AI strategy generator without touching
    the HTTP layer.

All queries are scoped to store_id so one store can never see another's data.
"""

import math
import uuid
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.normalized_sale import NormalizedSale


# ─── Helper ───────────────────────────────────────────────────────────────────

def _safe_float(value) -> float:
    """
    Convert Decimal or None to float safely.
    Also flattens NaN/inf to 0.0 — Postgres numeric columns can store NaN,
    and a single NaN poisons any SUM() it's part of, which then crashes
    FastAPI's JSON encoder ("Out of range float values are not JSON compliant").
    """
    try:
        result = float(value) if value is not None else 0.0
        return result if math.isfinite(result) else 0.0
    except (TypeError, ValueError):
        return 0.0


# ─── Summary ──────────────────────────────────────────────────────────────────

async def get_summary(store_id: uuid.UUID, db: AsyncSession) -> dict:
    """
    High-level KPIs for the store dashboard:
    total revenue, orders, units, AOV, top channel, date range, product count.
    """
    result = await db.execute(
        select(
            func.coalesce(func.sum(NormalizedSale.total_amount), 0).label("total_revenue"),
            func.count(NormalizedSale.id).label("total_orders"),
            func.coalesce(func.sum(NormalizedSale.quantity), 0).label("total_units"),
            func.min(NormalizedSale.sale_date).label("date_from"),
            func.max(NormalizedSale.sale_date).label("date_to"),
            func.count(func.distinct(NormalizedSale.product_name)).label("products_tracked"),
        ).where(NormalizedSale.store_id == store_id)
    )
    row = result.one()

    total_revenue = _safe_float(row.total_revenue)
    total_orders = row.total_orders or 0
    total_units = _safe_float(row.total_units)
    avg_order_value = round(total_revenue / total_orders, 2) if total_orders > 0 else 0.0

    # Find the channel with the highest revenue
    channel_result = await db.execute(
        select(
            NormalizedSale.channel,
            func.sum(NormalizedSale.total_amount).label("channel_revenue"),
        )
        .where(NormalizedSale.store_id == store_id)
        .group_by(NormalizedSale.channel)
        .order_by(func.sum(NormalizedSale.total_amount).desc())
        .limit(1)
    )
    top_channel_row = channel_result.one_or_none()

    return {
        "total_revenue": round(total_revenue, 2),
        "total_orders": total_orders,
        "total_units": round(total_units, 2),
        "average_order_value": avg_order_value,
        "top_channel": top_channel_row.channel if top_channel_row else None,
        "date_from": row.date_from,
        "date_to": row.date_to,
        "products_tracked": row.products_tracked or 0,
    }


# ─── Top products ─────────────────────────────────────────────────────────────

async def get_top_products(
    store_id: uuid.UUID,
    db: AsyncSession,
    limit: int = 10,
) -> list[dict]:
    """
    Top N products ranked by total revenue.
    Used to show the store owner what's selling best.
    """
    result = await db.execute(
        select(
            NormalizedSale.product_name,
            NormalizedSale.category,
            func.coalesce(func.sum(NormalizedSale.total_amount), 0).label("total_revenue"),
            func.coalesce(func.sum(NormalizedSale.quantity), 0).label("total_units"),
            func.count(NormalizedSale.id).label("order_count"),
        )
        .where(NormalizedSale.store_id == store_id)
        .group_by(NormalizedSale.product_name, NormalizedSale.category)
        .order_by(func.sum(NormalizedSale.total_amount).desc().nulls_last())
        .limit(limit)
    )

    return [
        {
            "product_name": row.product_name,
            "category": row.category,
            "total_revenue": round(_safe_float(row.total_revenue), 2),
            "total_units": round(_safe_float(row.total_units), 2),
            "order_count": row.order_count,
        }
        for row in result.all()
    ]


# ─── Slow-moving products ─────────────────────────────────────────────────────

async def get_slow_products(
    store_id: uuid.UUID,
    db: AsyncSession,
    limit: int = 10,
) -> list[dict]:
    """
    Bottom N products by total revenue — candidates for promotions.
    These are the products LiquorIQ's AI will suggest promoting in Phase 7.
    """
    result = await db.execute(
        select(
            NormalizedSale.product_name,
            NormalizedSale.category,
            func.coalesce(func.sum(NormalizedSale.total_amount), 0).label("total_revenue"),
            func.coalesce(func.sum(NormalizedSale.quantity), 0).label("total_units"),
            func.count(NormalizedSale.id).label("order_count"),
        )
        .where(NormalizedSale.store_id == store_id)
        .group_by(NormalizedSale.product_name, NormalizedSale.category)
        .order_by(func.sum(NormalizedSale.total_amount).asc().nulls_first())
        .limit(limit)
    )

    return [
        {
            "product_name": row.product_name,
            "category": row.category,
            "total_revenue": round(_safe_float(row.total_revenue), 2),
            "total_units": round(_safe_float(row.total_units), 2),
            "order_count": row.order_count,
        }
        for row in result.all()
    ]


# ─── Category performance ─────────────────────────────────────────────────────

async def get_category_performance(
    store_id: uuid.UUID,
    db: AsyncSession,
) -> list[dict]:
    """
    Revenue and units broken down by product category.
    Tells the owner which departments (Beer, Wine, Spirits, etc.) are strongest.
    """
    # Get total revenue first to calculate percentages
    total_result = await db.execute(
        select(func.coalesce(func.sum(NormalizedSale.total_amount), 0))
        .where(NormalizedSale.store_id == store_id)
    )
    total_revenue = _safe_float(total_result.scalar())

    result = await db.execute(
        select(
            NormalizedSale.category,
            func.coalesce(func.sum(NormalizedSale.total_amount), 0).label("total_revenue"),
            func.coalesce(func.sum(NormalizedSale.quantity), 0).label("total_units"),
            func.count(NormalizedSale.product_name.distinct()).label("product_count"),
        )
        .where(NormalizedSale.store_id == store_id)
        .group_by(NormalizedSale.category)
        .order_by(func.sum(NormalizedSale.total_amount).desc().nulls_last())
    )

    return [
        {
            "category": row.category or "Uncategorized",
            "total_revenue": round(_safe_float(row.total_revenue), 2),
            "total_units": round(_safe_float(row.total_units), 2),
            "product_count": row.product_count,
            "revenue_percentage": round(
                (_safe_float(row.total_revenue) / total_revenue * 100)
                if total_revenue > 0 else 0.0,
                1,
            ),
        }
        for row in result.all()
    ]


# ─── Channel performance ──────────────────────────────────────────────────────

async def get_channel_performance(
    store_id: uuid.UUID,
    db: AsyncSession,
) -> list[dict]:
    """
    Revenue, units, and order count broken down by sales channel
    (POS, Uber Eats, DoorDash, website, etc.)
    Shows which platforms are driving the most business.
    """
    total_result = await db.execute(
        select(func.coalesce(func.sum(NormalizedSale.total_amount), 0))
        .where(NormalizedSale.store_id == store_id)
    )
    total_revenue = _safe_float(total_result.scalar())

    result = await db.execute(
        select(
            NormalizedSale.channel,
            func.coalesce(func.sum(NormalizedSale.total_amount), 0).label("total_revenue"),
            func.coalesce(func.sum(NormalizedSale.quantity), 0).label("total_units"),
            func.count(NormalizedSale.id).label("order_count"),
        )
        .where(NormalizedSale.store_id == store_id)
        .group_by(NormalizedSale.channel)
        .order_by(func.sum(NormalizedSale.total_amount).desc().nulls_last())
    )

    return [
        {
            "channel": row.channel,
            "total_revenue": round(_safe_float(row.total_revenue), 2),
            "total_units": round(_safe_float(row.total_units), 2),
            "order_count": row.order_count,
            "revenue_percentage": round(
                (_safe_float(row.total_revenue) / total_revenue * 100)
                if total_revenue > 0 else 0.0,
                1,
            ),
        }
        for row in result.all()
    ]


# ─── Inventory Intelligence + Action Center (Phase 17) ───────────────────────

# Report period assumption + thresholds (tunable). AdvEntPOS summary reports are
# ~monthly, so weekly velocity ≈ period units / 4.3.
_PERIOD_WEEKS = 4.3
_REORDER_WEEKS = 2.0        # < 2 weeks of stock left → reorder soon
_OVERSTOCK_WEEKS = 16.0     # > ~4 months of stock → overstocked


async def get_inventory_intelligence(store_id: uuid.UUID, db: AsyncSession) -> dict:
    """
    Turn stock_on_hand + sales velocity into money + actions.

    Uses the LATEST snapshot per product (most recent sale_date) via Postgres
    DISTINCT ON. Classifies each product: dead / reorder-soon / overstocked /
    healthy, computes inventory value, and derives a ranked action list.
    """
    stmt = (
        select(
            NormalizedSale.product_name,
            NormalizedSale.category,
            NormalizedSale.quantity,
            NormalizedSale.unit_price,
            NormalizedSale.stock_on_hand,
            NormalizedSale.sale_date,
        )
        .where(NormalizedSale.store_id == store_id)
        .distinct(NormalizedSale.product_name)
        .order_by(NormalizedSale.product_name, NormalizedSale.sale_date.desc().nulls_last())
    )
    rows = (await db.execute(stmt)).all()

    inventory_value = 0.0
    has_stock_data = False
    products_in_stock = 0
    dead, reorder, overstock = [], [], []

    for r in rows:
        stock = _safe_float(r.stock_on_hand)
        price = _safe_float(r.unit_price)
        units = _safe_float(r.quantity)   # units sold in the latest period
        if r.stock_on_hand is not None:
            has_stock_data = True
        if stock <= 0:
            continue
        products_in_stock += 1

        value = round(stock * price, 2)
        inventory_value += value
        weekly = units / _PERIOD_WEEKS
        weeks_supply = (stock / weekly) if weekly > 0 else float("inf")

        item = {
            "product_name": r.product_name,
            "category": r.category,
            "stock": round(stock, 1),
            "value": value,
            "weeks_supply": (round(weeks_supply, 1) if weeks_supply != float("inf") else None),
            "units_last_period": round(units, 1),
        }
        if units <= 0:
            dead.append(item)
        elif weeks_supply < _REORDER_WEEKS:
            reorder.append(item)
        elif weeks_supply > _OVERSTOCK_WEEKS:
            overstock.append(item)

    dead.sort(key=lambda x: x["value"], reverse=True)
    reorder.sort(key=lambda x: (x["weeks_supply"] if x["weeks_supply"] is not None else 0))
    overstock.sort(key=lambda x: x["value"], reverse=True)

    dead_value = round(sum(i["value"] for i in dead), 2)
    overstock_value = round(sum(i["value"] for i in overstock), 2)

    # ── Derived action list ("do these today") ──
    actions = []
    if reorder:
        actions.append({
            "type": "reorder", "severity": "high",
            "title": f"Reorder {len(reorder)} product{'s' if len(reorder) != 1 else ''} running low",
            "detail": ", ".join(i["product_name"] for i in reorder[:3]),
        })
    if dead:
        actions.append({
            "type": "dead", "severity": "high",
            "title": f"${dead_value:,.0f} frozen in {len(dead)} dead-stock product{'s' if len(dead) != 1 else ''}",
            "detail": "Promote or discount to free up cash",
            "cta": "Generate a clearance campaign", "link": "/ai",
        })
    if overstock:
        actions.append({
            "type": "overstock", "severity": "medium",
            "title": f"{len(overstock)} product{'s' if len(overstock) != 1 else ''} overstocked",
            "detail": ", ".join(i["product_name"] for i in overstock[:3]),
            "cta": "Run a promotion", "link": "/ai",
        })

    return {
        "has_stock_data": has_stock_data,
        "inventory_value": round(inventory_value, 2),
        "products_in_stock": products_in_stock,
        "dead_stock": {"count": len(dead), "value": dead_value, "items": dead[:10]},
        "reorder_soon": {"count": len(reorder), "items": reorder[:10]},
        "overstocked": {"count": len(overstock), "value": overstock_value, "items": overstock[:10]},
        "actions": actions,
    }
