"""schemas/label_studio.py — MODULE 2: LABEL STUDIO request/response shapes."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class LabelIn(BaseModel):
    """The label spec. Loosely typed on purpose — shelf_label.validate_label()
    is the single source of truth for coercion, so the rules live in one place."""
    spec: dict = Field(default_factory=dict)
    # PHASE 23.8: set when the label is made from inside a campaign. Optional —
    # the Label Studio is also a standalone tool.
    strategy_id: uuid.UUID | None = Field(
        default=None, description="The campaign this label belongs to, if any")


class SheetIn(BaseModel):
    """Print N labels per page; the page is divided into that many equal cells."""
    label_ids: list[uuid.UUID] = Field(min_length=1, max_length=120)
    per_page: int = Field(default=4, description="2, 4, 6, 9 or 12 labels per sheet")
    page: str = Field(default="a4", pattern="^(a4|letter)$")
    orientation: str = Field(default="landscape", pattern="^(portrait|landscape)$",
                             description="Turns the PAPER; the grid transposes with it")
    repeat: bool = Field(default=False, description="Repeat the selection to fill one page")
    cut_marks: bool = Field(default=True, description="Print cut guides and crop ticks")


class TemplateIn(BaseModel):
    spec: dict = Field(default_factory=dict)
    name: str = Field(default="", max_length=40)


class ApplyTemplateIn(BaseModel):
    """Put this label's content into the chosen template's look."""
    spec: dict = Field(default_factory=dict)


class LabelOut(BaseModel):
    id: uuid.UUID
    store_id: uuid.UUID
    strategy_id: uuid.UUID | None = None
    name: str
    design_json: dict
    final_image_url: str | None = None
    is_template: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProductSuggestion(BaseModel):
    """Prefill from the store's own POS history."""
    product_name: str
    price: str = ""
    units_sold: int = 0
