"""
services/creative_service.py — Ad creative generation pipeline (Phase 10)

Pipeline (one call to generate_ad_creative does all of this):
  1. Load the strategy (must belong to the requesting store — auth boundary)
  2. GPT-4o call #1: turn the strategy into platform-specific copy
     (Instagram, Facebook, Uber Eats, DoorDash, website banner)
     PLUS a "image_prompt" field — a DALL-E-ready art-direction prompt
  3. DALL-E 3 call: generate the 1024x1024 ad image from that prompt
  4. Save the PNG to disk (settings.creatives_dir, served at /static/creatives)
  5. Save everything to ad_creatives and return the ORM object

Why let GPT-4o write the DALL-E prompt instead of templating one ourselves?
  GPT-4o knows the strategy context (products, offer, audience) and writes a
  far richer art-direction prompt than any f-string template could. We save
  the prompt to the DB so every image is fully auditable/reproducible.

Cost note: one creative = 1 GPT-4o call (~$0.01) + 1 DALL-E 3 standard
image ($0.04) ≈ $0.05 per generation.
"""

import json
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import func

from app.config import get_settings
from app.models.ad_creative import AdCreative
from app.models.ai_strategy_report import AIStrategyReport
from app.models.normalized_sale import NormalizedSale
from app.models.store import Store
from app.services.compose_service import render_final_ad
from app.services.openai_service import generate_image, generate_json_response
from app.services.storage_service import fetch_image, save_image

logger = logging.getLogger(__name__)
settings = get_settings()

# ─── Prompt templates ──────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a senior creative director at an ad agency that
specializes in local retail — specifically independent liquor stores. You turn
promotion strategies into scroll-stopping, platform-native ad copy.

Platform rules you always follow:
  - instagram_caption: punchy, 1-3 short lines, 3-5 relevant hashtags at the
    end, one tasteful emoji allowed. Must include a call to action.
  - facebook_post: 2-4 sentences, warmer/community tone, mention the offer
    explicitly, end with a call to action. No hashtags.
  - ubereats_description: 1-2 sentences for a delivery app promo banner.
    Focus on convenience + the deal. No hashtags, no emojis.
  - doordash_description: 1-2 sentences, similar to Uber Eats but not
    identical wording. No hashtags, no emojis.
  - website_banner_headline: max 8 words, high impact.
  - website_banner_text: one supporting sentence with the offer + urgency.
  - image_prompt: an art-direction prompt for an AI image generator.
    Describe a premium promotional product photograph: the bottles/products
    on a styled surface, lighting, mood, background, color palette. DO NOT
    include any text, words, letters, logos, or human faces in the image
    description (AI image models render text badly). Never mention brand
    names — describe generic bottle shapes and drink types instead.

Alcohol advertising rules: never target minors, never encourage excessive
drinking, keep everything classy.

Always respond with valid JSON matching EXACTLY this schema — no extra keys,
no missing keys:
{
  "image_prompt": "string",
  "instagram_caption": "string",
  "facebook_post": "string",
  "ubereats_description": "string",
  "doordash_description": "string",
  "website_banner_headline": "string",
  "website_banner_text": "string"
}"""


def _build_user_prompt(strategy: AIStrategyReport) -> str:
    """Feed the full strategy context so the copy is grounded in real data."""
    products = json.dumps(strategy.products_to_promote)
    return f"""Store: {strategy.store_name}

Promotion strategy to turn into ad creative:
  - Campaign: {strategy.strategy_title}
  - Products to promote: {products}
  - Offer: {strategy.recommended_offer}
  - Target customers: {strategy.target_customer_segment}
  - Why we're running this: {strategy.reason}

Generate the complete ad creative package (all platforms + image_prompt).
Use the actual product names in the copy. The tone should make a small
neighborhood liquor store feel premium but approachable."""


# ─── Required fields validation ────────────────────────────────────────────────

REQUIRED_FIELDS = {
    "image_prompt",
    "instagram_caption",
    "facebook_post",
    "ubereats_description",
    "doordash_description",
    "website_banner_headline",
    "website_banner_text",
}


def _validate_creative(data: dict) -> None:
    """Raise ValueError if any required field is missing or empty."""
    missing = REQUIRED_FIELDS - set(data.keys())
    if missing:
        raise ValueError(f"OpenAI response missing fields: {missing}")
    empty = [k for k in REQUIRED_FIELDS if not data.get(k)]
    if empty:
        raise ValueError(f"OpenAI response has empty fields: {empty}")


# ─── Public service functions ──────────────────────────────────────────────────

async def generate_ad_creative(
    strategy_id: uuid.UUID,
    store_id: uuid.UUID,
    db: AsyncSession,
) -> AdCreative:
    """
    Full pipeline: strategy → GPT-4o copy → DALL-E image → disk → DB.

    Raises:
        ValueError   — strategy not found / bad AI response
        RuntimeError — OpenAI API failure (surfaced as 502 by the route)
    """
    # 1. Load the strategy, scoped to this store (prevents cross-store access)
    result = await db.execute(
        select(AIStrategyReport).where(
            AIStrategyReport.id == strategy_id,
            AIStrategyReport.store_id == store_id,
        )
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise ValueError("Strategy not found")

    logger.info("Generating ad creative for strategy=%s", strategy_id)

    # 2. GPT-4o: platform copy + DALL-E prompt
    ai_data = await generate_json_response(
        SYSTEM_PROMPT,
        _build_user_prompt(strategy),
    )
    _validate_creative(ai_data)

    # 3. DALL-E 3: generate the ad image (square 1024x1024 — works on every platform)
    png_bytes = await generate_image(prompt=ai_data["image_prompt"])

    # 4. Persist image (local disk in dev, Cloudinary CDN in prod)
    image_url = await save_image(png_bytes, prefix="ad")
    logger.info("Ad image saved: %s (%d KB)", image_url, len(png_bytes) // 1024)

    # 5. Save to DB
    creative = AdCreative(
        store_id=store_id,
        strategy_id=strategy_id,
        image_prompt=ai_data["image_prompt"],
        image_url=image_url,
        instagram_caption=ai_data["instagram_caption"],
        facebook_post=ai_data["facebook_post"],
        ubereats_description=ai_data["ubereats_description"],
        doordash_description=ai_data["doordash_description"],
        website_banner_headline=ai_data["website_banner_headline"],
        website_banner_text=ai_data["website_banner_text"],
        model_used=f"{settings.openai_model} + {settings.openai_image_model}",
    )
    db.add(creative)
    await db.commit()
    await db.refresh(creative)

    logger.info("Ad creative saved: id=%s", creative.id)
    return creative


async def get_price_suggestions(
    strategy_id: uuid.UUID,
    store_id: uuid.UUID,
    db: AsyncSession,
) -> list[dict]:
    """
    For each promoted product, look up its most recent unit_price from the
    store's real sales data. This is the moat in miniature: ChatGPT doesn't
    know your prices — your POS data does. Owner can still edit before compose.

    Returns [{"product_name": str, "price": float | None}] — None when no
    matching sale row exists (AI occasionally rephrases a product name).
    """
    result = await db.execute(
        select(AIStrategyReport).where(
            AIStrategyReport.id == strategy_id,
            AIStrategyReport.store_id == store_id,
        )
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise ValueError("Strategy not found")

    suggestions: list[dict] = []
    for name in strategy.products_to_promote:
        row = await db.execute(
            select(NormalizedSale.unit_price)
            .where(
                NormalizedSale.store_id == store_id,
                func.lower(NormalizedSale.product_name) == str(name).lower(),
                NormalizedSale.unit_price.isnot(None),
            )
            .order_by(NormalizedSale.sale_date.desc())
            .limit(1)
        )
        price = row.scalar_one_or_none()
        suggestions.append({
            "product_name": str(name),
            "price": float(price) if price is not None else None,
        })
    return suggestions


async def compose_final_creative(
    creative_id: uuid.UUID,
    store_id: uuid.UUID,
    items: list[dict],
    db: AsyncSession,
) -> AdCreative:
    """
    Compose the final postable ad: original AI background + Pillow overlay of
    the owner-confirmed names and prices. Saves the composed PNG via the
    storage backend and records final_image_url + price_items on the creative.

    Raises:
        ValueError   — creative not found / original image missing
        RuntimeError — storage upload failure
    """
    result = await db.execute(
        select(AdCreative).where(
            AdCreative.id == creative_id,
            AdCreative.store_id == store_id,
        )
    )
    creative = result.scalar_one_or_none()
    if not creative:
        raise ValueError("Creative not found")

    store_row = await db.execute(select(Store).where(Store.id == store_id))
    store = store_row.scalar_one_or_none()

    # 1. Original AI background (disk in dev, Cloudinary in prod)
    background = await fetch_image(creative.image_url)

    # 2. Deterministic overlay — exact names, exact prices
    final_png = await render_final_ad(
        background_png=background,
        headline=creative.website_banner_headline,
        items=items,
        store_name=store.name if store else "",
    )

    # 3. Persist + record
    final_url = await save_image(final_png, prefix="final")
    creative.final_image_url = final_url
    creative.price_items = items
    await db.commit()
    await db.refresh(creative)

    logger.info("Final ad composed: creative=%s url=%s", creative.id, final_url)
    return creative


async def get_latest_creative_for_strategy(
    strategy_id: uuid.UUID,
    store_id: uuid.UUID,
    db: AsyncSession,
) -> AdCreative | None:
    """Newest creative for a strategy (regeneration keeps history; we show the latest)."""
    result = await db.execute(
        select(AdCreative)
        .where(
            AdCreative.strategy_id == strategy_id,
            AdCreative.store_id == store_id,
        )
        .order_by(AdCreative.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()
