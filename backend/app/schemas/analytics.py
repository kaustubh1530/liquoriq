"""
schemas/analytics.py — Pydantic response schemas for all analytics endpoints

These define exactly what the API returns for each analytics query.
The frontend React dashboard (Phase 8) will consume these shapes directly.
"""

from datetime import date
from pydantic import BaseModel


# ─── GET /analytics/summary ───────────────────────────────────────────────────

class SummaryResponse(BaseModel):
    total_revenue: float
    total_orders: int          # number of line items in normalized_sales
    total_units: float
    average_order_value: float # total_revenue / total_orders
    top_channel: str | None    # channel with highest revenue
    date_from: date | None     # earliest sale_date in the dataset
    date_to: date | None       # latest sale_date in the dataset
    products_tracked: int      # distinct product names


# ─── GET /analytics/top-products & /analytics/slow-products ──────────────────

class ProductPerformance(BaseModel):
    product_name: str
    category: str | None
    total_revenue: float
    total_units: float
    order_count: int           # how many rows reference this product


# ─── GET /analytics/category-performance ─────────────────────────────────────

class CategoryPerformance(BaseModel):
    category: str
    total_revenue: float
    total_units: float
    product_count: int         # distinct products in this category
    revenue_percentage: float  # share of total store revenue


# ─── GET /analytics/channel-performance ──────────────────────────────────────

class ChannelPerformance(BaseModel):
    channel: str
    total_revenue: float
    total_units: float
    order_count: int
    revenue_percentage: float  # share of total store revenue