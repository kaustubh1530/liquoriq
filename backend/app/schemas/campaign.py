"""
schemas/campaign.py — Campaign ROI tracking responses (Phase 12)

GET /ai/strategies/{id}/performance → CampaignPerformanceResponse

status values:
  no_baseline — no sales history for these products before the strategy
  measuring   — inside the campaign window; numbers are partial
  complete    — window over; numbers are final
Lift fields are None when there's no baseline to compare against.
"""

import uuid
from datetime import date

from pydantic import BaseModel


class ProductCampaignResult(BaseModel):
    product_name: str
    baseline_weekly_units: float
    baseline_weekly_revenue: float
    campaign_weekly_units: float
    campaign_weekly_revenue: float
    units_lift_pct: float | None = None
    revenue_lift: float | None = None    # $ vs what baseline predicted


class CampaignPerformanceResponse(BaseModel):
    strategy_id: uuid.UUID
    status: str                          # no_baseline | measuring | complete
    campaign_start: date
    campaign_end: date
    days_elapsed: int
    campaign_window_days: int
    baseline_window_days: int
    products: list[ProductCampaignResult]
    total_units_lift_pct: float | None = None
    total_revenue_lift: float | None = None
