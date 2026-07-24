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
    Options for generating a campaign (Strategy 2.0).
    - limit: how many slow movers to include as secondary clearance context
    - deal_id: if set, the campaign is built around that supplier deal buy
    """
    limit: int = Field(default=5, ge=1, le=20)
    deal_ids: list[uuid.UUID] | None = Field(
        default=None,
        description="Center the campaign on these deal buys (one, or several closeouts bundled together)",
    )
    occasion: str | None = Field(
        default=None, max_length=120,
        description="Event/holiday to build around (e.g. 'Halloween', 'a wedding', 'store anniversary')",
    )
    instructions: str | None = Field(
        default=None, max_length=600,
        description="Free-text brief: new-release item to push, a specific offer/price, target audience, etc.",
    )


# ─── GET /ai/strategies  &  GET /ai/strategies/{id} ──────────────────────────

class StrategyResponse(BaseModel):
    """
    Full AI strategy report returned to the client.
    Mirrors every column in ai_strategy_reports exactly.
    """
    id: uuid.UUID
    store_id: uuid.UUID

    # What was sent to the AI (Strategy 2.0: an object with top_products + deals)
    store_name: str
    products_analyzed: Any

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

    # Strategy 2.0 (Phase 15)
    occasion: str | None = None
    strategy_type: str | None = None
    offline_plan: str | None = None
    online_plan: str | None = None
    vivino_listing: str | None = None

    # Meta
    model_used: str
    created_at: datetime

    # protected_namespaces=() silences the pydantic "model_" prefix warning
    model_config = {"from_attributes": True, "protected_namespaces": ()}


class StrategyListItem(BaseModel):
    """
    Lightweight version for listing multiple strategies (no big text fields).
    Only used for GET /ai/strategies list view.
    """
    id: uuid.UUID
    strategy_title: str
    products_to_promote: list[Any]
    recommended_offer: str
    occasion: str | None = None
    strategy_type: str | None = None
    model_used: str
    created_at: datetime

    model_config = {"from_attributes": True, "protected_namespaces": ()}