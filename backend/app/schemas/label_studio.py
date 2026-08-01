"""schemas/label_studio.py — MODULE 2: LABEL STUDIO request/response shapes."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class LabelIn(BaseModel):
    """The label spec. Loosely typed on purpose — shelf_label.validate_label()
    is the single source of truth for coercion, so the rules live in one place."""
    spec: dict = Field(default_factory=dict)


class SheetIn(BaseModel):
    label_ids: list[uuid.UUID] = Field(min_length=1, max_length=60)
    size: str | None = Field(default=None, description="Override; defaults to the first label's size")


class LabelOut(BaseModel):
    id: uuid.UUID
    store_id: uuid.UUID
    name: str
    design_json: dict
    final_image_url: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProductSuggestion(BaseModel):
    """Prefill from the store's own POS history."""
    product_name: str
    price: str = ""
    units_sold: int = 0
