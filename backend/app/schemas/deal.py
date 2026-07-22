"""schemas/deal.py — Supplier deal-buy shapes (Phase 15)"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class DealCreate(BaseModel):
    product_name: str = Field(min_length=1, max_length=500)
    category: str | None = Field(default=None, max_length=200)
    cost_price: float = Field(gt=0, lt=100_000, description="What you paid per unit")
    normal_price: float | None = Field(default=None, gt=0, lt=100_000)
    quantity: float | None = Field(default=None, ge=0, lt=1_000_000)
    note: str | None = None
    expires_on: date | None = None


class DealResponse(BaseModel):
    id: uuid.UUID
    product_name: str
    category: str | None
    cost_price: float
    normal_price: float | None
    quantity: float | None
    note: str | None
    expires_on: date | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
