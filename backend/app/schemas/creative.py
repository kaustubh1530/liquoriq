"""
schemas/creative.py — Request/response shapes for ad creative endpoints

POST /creative/generate  — body: GenerateCreativeRequest → 201 CreativeResponse
GET  /creative/{strategy_id} — latest CreativeResponse for that strategy
"""

import uuid
from datetime import datetime

from pydantic import BaseModel


# ─── POST /creative/generate ──────────────────────────────────────────────────

class GenerateCreativeRequest(BaseModel):
    """The strategy to build a creative package for."""
    strategy_id: uuid.UUID


# ─── Responses ────────────────────────────────────────────────────────────────

class CreativeResponse(BaseModel):
    """
    Full ad creative package. Mirrors every column in ad_creatives.
    image_url is relative — the frontend prepends nothing in dev
    (Vite proxy) and the API base URL in production.
    """
    id: uuid.UUID
    store_id: uuid.UUID
    strategy_id: uuid.UUID

    image_prompt: str
    image_url: str

    instagram_caption: str
    facebook_post: str
    ubereats_description: str
    doordash_description: str
    website_banner_headline: str
    website_banner_text: str

    model_used: str
    created_at: datetime

    model_config = {"from_attributes": True}
