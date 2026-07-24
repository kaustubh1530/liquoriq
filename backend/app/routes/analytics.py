"""
routes/analytics.py — Analytics endpoints

All endpoints are protected (require JWT) and scoped to the logged-in
user's store. They read from normalized_sales — so data only appears here
after a report has been uploaded (Phase 4) and parsed (Phase 5).

GET /analytics/summary             — KPI overview (revenue, orders, AOV)
GET /analytics/top-products        — best-selling products by revenue
GET /analytics/slow-products       — worst-selling products (promo candidates)
GET /analytics/category-performance — revenue by category (Beer, Wine, etc.)
GET /analytics/channel-performance  — revenue by channel (POS, Uber, etc.)
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.store import Store
from app.routes.stores import get_current_store
from app.schemas.analytics import (
    CategoryPerformance,
    ChannelPerformance,
    ProductPerformance,
    SummaryResponse,
)
from app.services.analytics_service import (
    get_category_performance,
    get_channel_performance,
    get_inventory_intelligence,
    get_slow_products,
    get_summary,
    get_top_products,
)

router = APIRouter()


@router.get(
    "/inventory",
    summary="Inventory Intelligence + Action Center (value, dead stock, reorder, overstock)",
)
async def analytics_inventory(
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await get_inventory_intelligence(current_store.id, db)


@router.get(
    "/summary",
    response_model=SummaryResponse,
    summary="Overall KPIs — total revenue, orders, units, and date range",
)
async def analytics_summary(
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await get_summary(store_id=current_store.id, db=db)


@router.get(
    "/top-products",
    response_model=list[ProductPerformance],
    summary="Top products ranked by total revenue",
)
async def analytics_top_products(
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=10, ge=1, le=50, description="Number of products to return"),
) -> list[dict]:
    return await get_top_products(store_id=current_store.id, db=db, limit=limit)


@router.get(
    "/slow-products",
    response_model=list[ProductPerformance],
    summary="Slow-moving products — lowest revenue, best candidates for promotion",
)
async def analytics_slow_products(
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=10, ge=1, le=50, description="Number of products to return"),
) -> list[dict]:
    return await get_slow_products(store_id=current_store.id, db=db, limit=limit)


@router.get(
    "/category-performance",
    response_model=list[CategoryPerformance],
    summary="Revenue and units broken down by product category",
)
async def analytics_category_performance(
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await get_category_performance(store_id=current_store.id, db=db)


@router.get(
    "/channel-performance",
    response_model=list[ChannelPerformance],
    summary="Revenue and units broken down by sales channel (POS, Uber Eats, etc.)",
)
async def analytics_channel_performance(
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await get_channel_performance(store_id=current_store.id, db=db)