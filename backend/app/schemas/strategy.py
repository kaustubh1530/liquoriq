"""
schemas/strategy.py — Request/response shapes for AI strategy endpoints

Why a separate schema file?
  The AI output has 10 fields (sms_copy, email_body, etc.) — too long to
  mix into analytics.py. Keeping it isolated also makes it easy to version
  the schema (StrategyResponseV2) if we ever change the output format.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ─── POST /ai/generate-promotion ──────────────────────────────────────────────

class GeneratePromotionRequest(BaseModel):
    """
    Optional filters the store owner can pass when requesting a promotion.
    If limit is omitted, we default to top 5 slow-moving products.
    """
    limit: int = Field(
        default=5,
        ge=1,
        le=20,
        description="How many slow-moving products to include in the AI context",
    )


# ─── GET /ai/strategies  &  GET /ai/strategies/{id} ──────────────────────────

class StrategyResponse(BaseModel):
    """
    Full AI strategy report returned to the client.
    Mirrors every column in ai_strategy_reports exactly.
    """
    id: uuid.UUID
    store_id: uuid.UUID

    # What was sent to the AI
    store_name: str
    products_analyzed: list[Any]        # list of dicts with product data

    # AI-generated promotion plan
    strategy_title: str
    products_to_promote: list[Any]      # list of product name strings
    reason: str
    target_customer_segment: str
    recommended_offer: str
    sms_copy: str
    email_subject: str
    email_body: str
    social_caption: str
    expected_impact: str

    # Meta
    model_used: str
    created_at: datetime

    model_config = {"from_attributes": True}


class StrategyListItem(BaseModel):
    """
    Lightweight version for listing multiple strategies (no big text fields).
    Only used for GET /ai/strategies list view.
    """
    id: uuid.UUID
    strategy_title: str
    products_to_promote: list[Any]
    recommended_offer: str
    model_used: str
    created_at: datetime

    model_config = {"from_attributes": True}