"""
schemas/creative.py — Request/response shapes for ad creative endpoints

POST /creative/generate                → 201 CreativeResponse
GET  /creative/{strategy_id}           → latest CreativeResponse
GET  /creative/{strategy_id}/prices    → list[PriceSuggestion]   (Phase 11)
POST /creative/{creative_id}/compose   → CreativeResponse w/ final_image_url (Phase 11)
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field  # noqa: F401


# ─── POST /creative/generate ──────────────────────────────────────────────────

class GenerateCreativeRequest(BaseModel):
    """The strategy to build a creative package for."""
    strategy_id: uuid.UUID
    offer_override: str | None = Field(
        default=None, max_length=200,
        description="Exact promo price/offer to render on the ad (defaults to the strategy's offer)",
    )
    instructions: str | None = Field(
        default=None, max_length=600,
        description="Owner's art-direction hints: theme, event, layout, mood, changes to make",
    )
    product_image_url: str | None = Field(
        default=None,
        description="Phase 16: a real product photo (from POST /creative/product-photo) to use as the accurate hero",
    )
    image_format: str = Field(
        default="square", pattern="^(square|portrait|landscape)$",
        description="square (social), portrait (print/A4 poster), or landscape (banner)",
    )
    product_facts: dict | None = Field(
        default=None,
        description="Owner-confirmed product facts for THIS generation (else the saved facts are used)",
    )
    campaign_type: str = Field(
        default="standard",
        pattern="^(standard|new_arrival|product_spotlight|premium_collection|limited_edition)$",
        description="Product details appear automatically for the four product-led types",
    )
    show_product_details: bool = Field(
        default=False,
        description="Owner explicitly opts in to showing product details on the ad",
    )
    ad_layout: str = Field(
        default="auto",
        pattern="^(auto|poster|rail|band|banner)$",
        description="How the text is typeset over the scene; auto suits it to the format",
    )


class ProductFactsIn(BaseModel):
    product_name: str = Field(min_length=1, max_length=500)
    category: str | None = Field(default=None, max_length=100)
    facts: dict = Field(default_factory=dict)


# ─── Phase 11: price overlay ──────────────────────────────────────────────────

class PriceSuggestion(BaseModel):
    """Prefill row: latest unit_price from the store's own sales data."""
    product_name: str
    price: float | None = None    # None = product name not found in sales rows


class PriceItem(BaseModel):
    """Owner-confirmed row used in the final composed ad."""
    product_name: str = Field(min_length=1, max_length=200)
    price: float = Field(gt=0, lt=100_000)


class ComposeRequest(BaseModel):
    """Prices to stamp onto the ad. Max 5 rows are rendered."""
    items: list[PriceItem] = Field(min_length=1, max_length=10)


# ─── Responses ────────────────────────────────────────────────────────────────

class CreativeResponse(BaseModel):
    """
    Full ad creative package. image_url = original AI background;
    final_image_url = composed ad with the deterministic price overlay
    (null until the owner composes one).
    """
    id: uuid.UUID
    store_id: uuid.UUID
    strategy_id: uuid.UUID

    image_prompt: str
    image_url: str
    final_image_url: str | None = None
    price_items: list | None = None
    design_plan: dict | None = None
    design_json: dict | None = None

    instagram_caption: str
    facebook_post: str
    ubereats_description: str
    doordash_description: str
    website_banner_headline: str
    website_banner_text: str

    model_used: str
    created_at: datetime

    # protected_namespaces=() silences pydantic's warning that "model_used"
    # collides with its reserved "model_" prefix — it's just a warning, but
    # clean logs matter.
    model_config = {"from_attributes": True, "protected_namespaces": ()}
