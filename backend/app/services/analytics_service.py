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
