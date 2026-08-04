"""
services/creative_service.py — MODULE 1: AI AD CREATOR

RESPONSIBILITY: produce ONE beautiful, finished, ready-to-post advertisement.
It ends there. It does not know what a badge is.

Pipeline (one call to generate_ad_creative does all of this):
  1. Load the strategy (must belong to the requesting store — auth boundary)
  2. GPT-4o: strategy → STRUCTURED design plan + platform copy
  3. design_plan.validate_design_plan(): deterministic scrub/caps/fact-gating
  4. gpt-image-1: render the SCENE + HERO PRODUCT only — no text, no badges
  5. ad_text_renderer: stamp the headline, EXACT price, store name (and, only
     when gated on, a few product details) with Pillow
  6. Save the finished ad to ad_creatives and return the ORM object

The finished ad contains: attractive background, correct product, premium
lighting, professional composition, exact selling price, store name, headline.
Badges / stickers / ribbons / deal labels / coupons are NOT produced here —
they belong to MODULE 2, the Label Studio (services/shelf_label.py), which makes
printable shelf labels and never touches this image.

Cost note: one creative = 1 GPT-4o call (~$0.01) + 1 gpt-image-1 image
(~$0.04-0.19 at quality=high). The Pillow text layer is free.
"""

import json
import logging
import random
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
from app.services.openai_service import generate_image, generate_image_edit, generate_json_response
from app.services.storage_service import fetch_image, save_image


def _to_png(image_bytes: bytes, max_side: int = 1024) -> bytes:
    """Normalize any uploaded photo to a square-ish PNG for the edit API."""
    from io import BytesIO

    from PIL import Image

    img = Image.open(BytesIO(image_bytes)).convert("RGBA")
    img.thumbnail((max_side, max_side))
    # gpt-image-1 edit expects a square canvas; pad transparent to 1024x1024
    canvas = Image.new("RGBA", (max_side, max_side), (0, 0, 0, 0))
    canvas.paste(img, ((max_side - img.width) // 2, (max_side - img.height) // 2))
    out = BytesIO()
    canvas.save(out, format="PNG")
    return out.getvalue()

logger = logging.getLogger(__name__)
settings = get_settings()

# ─── Prompt templates ──────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a senior art director at a top ad agency, art-directing
a PROFESSIONAL advertisement photograph for an independent liquor store — the
quality of a paid agency campaign.

You produce a STRUCTURED DESIGN PLAN plus platform copy.

CRITICAL DIVISION OF LABOUR: you direct the PHOTOGRAPH only — the scene, the
product, the lighting, the composition, the palette. You do NOT design text
placement, and you NEVER call for badges, stickers, ribbons, banners, seals,
starbursts, price tags, discount cards, coupons, or sale labels. The headline,
price and store name are typeset separately by our own renderer, and promotional
badges are added later by the store owner in a separate editor.

Design principles you always follow:
  - ONE clear focal point: the hero bottle, sharply lit, on the RIGHT of frame.
  - A RICH, ATTRACTIVE, atmospheric themed scene (real depth, props, mood) that
    makes the ad eye-catching — kept slightly softer behind the product so the
    bottle stays the hero. Never plain or empty.
  - The LEFT THIRD stays visually calm (darker or softly blurred) because a
    caption is typeset there afterwards.
  - A bold, cohesive colour palette matched to the occasion (never default to
    warm amber every time).

FACTS RULE: use ONLY product facts explicitly provided to you. NEVER invent a
proof, ABV, age, award, origin, distillery, region, ingredients, or bottle size.
If a fact isn't provided, omit it — do not guess.
FORBIDDEN: never mention cost, margin, markup, wholesale, or profit anywhere.
Adults 25+ only; classy; never depict excessive drinking.

Design-plan fields:
  eyebrow           — 1-3 word kicker above the headline (e.g. "NOW IN STORE",
                      "LABOR DAY", "NEW ARRIVAL") — or empty
  headline          — the campaign/occasion hook, ≤6 words, punchy (we typeset it)
  subheadline       — one short supporting line (or empty)
  accent_color      — a HEX colour ("#c1121f") pulled FROM the scene you just
                      art-directed: the shade our typography and price block
                      should use so the caption belongs to this photograph.
                      Must contrast well against white text.
  visual_theme      — the mood/setting in a phrase
  palette           — 2-3 colours matched to the occasion
  typography_style  — the type mood we should match when typesetting
  product_placement — where/how the hero bottle sits
  product_details   — array of ≤3 SHORT customer-facing fact/benefit phrases,
                      using ONLY confirmed facts (may be shown or suppressed)
  background        — a rich, attractive, atmospheric themed scene (never plain)
  lighting          — cinematic lighting description
  composition       — layout notes (focal point, negative space on the left)

Platform copy rules: instagram_caption (punchy, 3-5 hashtags, 1 emoji, CTA);
facebook_post (2-4 warm sentences + CTA, no hashtags); ubereats_description and
doordash_description (1-2 sentences, distinct, no hashtags/emojis);
website_banner_headline (≤8 words); website_banner_text (one urgency sentence).

Respond with valid JSON EXACTLY:
{
  "design_plan": {
    "eyebrow": "string", "headline": "string", "subheadline": "string",
    "visual_theme": "string", "palette": "string", "accent_color": "#rrggbb",
    "typography_style": "string", "product_placement": "string",
    "product_details": ["string"],
    "background": "string", "lighting": "string", "composition": "string"
  },
  "instagram_caption": "string",
  "facebook_post": "string",
  "ubereats_description": "string",
  "doordash_description": "string",
  "website_banner_headline": "string",
  "website_banner_text": "string"
}"""


def _choose_hero(strategy, offer_override: str | None) -> str | None:
    """
    Which bottle the ad should show.

    Not simply products_to_promote[0]. When the offer names one of the promoted
    products — "…get Lamarca Prosecco for $14.99" — THAT is the bottle the
    price belongs to, and showing any other bottle beside that price advertises
    a price the store doesn't offer. Falls back to the first promoted product
    when the offer names none of them.
    """
    from app.services import design_plan as dp

    products = [str(p) for p in (strategy.products_to_promote or [])]
    offer = (offer_override or "").strip() or (strategy.recommended_offer or "")
    return dp.find_offer_subject(offer, products) or (products[0] if products else None)


async def _known_unit_price(store_id, product_name: str, db) -> float | None:
    """
    What the POS says this product last sold for.

    Used ONLY to reject an advertised price that cannot belong to this bottle.
    Never used to fill one in: the store sets its own prices, and a figure the
    owner didn't approve has no business on his advertising.
    """
    try:
        from sqlalchemy import select

        from app.models.normalized_sale import NormalizedSale

        row = (await db.execute(
            select(NormalizedSale.unit_price)
            .where(NormalizedSale.store_id == store_id,
                   NormalizedSale.product_name.ilike(product_name),
                   NormalizedSale.unit_price.isnot(None))
            .order_by(NormalizedSale.sale_date.desc().nulls_last())
            .limit(1)
        )).scalars().first()
        return float(row) if row else None
    except Exception:  # noqa: BLE001 — a missing price must never block an ad
        logger.warning("Could not look up a reference price for %s", product_name,
                       exc_info=True)
        return None


def _strip_internal_numbers(offer: str) -> str:
    """
    Remove owner-only clauses (margin/cost/profit) from the offer before it can
    reach the IMAGE. Customers must only ever see the sale price or discount.
    Splits the offer on separators and drops any clause mentioning those terms.
    e.g. "BOGO free — still 55% margin at $2 cost" → "BOGO free".
    """
    import re
    INTERNAL = re.compile(r"\b(margin|cost|profit|markup|wholesale)\b", re.I)
    # Split on ( ) [ ] — , ; while keeping customer-facing clauses
    clauses = re.split(r"[()\[\]—;]|,(?=\s)", offer)
    kept = [c.strip() for c in clauses if c.strip() and not INTERNAL.search(c)]
    result = ", ".join(kept)
    return re.sub(r"\s{2,}", " ", result).strip(" -—,;") or offer.split("(")[0].strip()


def _build_user_prompt(
    strategy: AIStrategyReport,
    offer_override: str | None = None,
    instructions: str | None = None,
    product_facts: dict | None = None,
    campaign_type: str | None = None,
) -> str:
    """Feed strategy + confirmed product facts so the plan is grounded, not invented."""
    product_list = list(strategy.products_to_promote or [])
    hero = product_list[0] if product_list else "the promoted bottle"
    occasion = strategy.occasion or strategy.strategy_title
    base_offer = offer_override.strip() if offer_override and offer_override.strip() else strategy.recommended_offer
    customer_offer = _strip_internal_numbers(base_offer)
    owner_hint = (instructions or "").strip()

    facts_txt = "None provided — DO NOT invent any product facts."
    if product_facts:
        confirmed = {k: v for k, v in product_facts.items() if v}
        if confirmed:
            facts_txt = json.dumps(confirmed)

    variety = random.choice([
        "wide establishing composition with the product on the right third",
        "clean modern studio-meets-lifestyle look with one bold accent colour",
        "dramatic low-angle hero shot with strong rim lighting on a dark backdrop",
        "bright airy daylight lifestyle scene with shallow depth of field",
        "premium editorial layout with lots of negative space",
    ])

    return f"""Store: {strategy.store_name}
Occasion / theme: {occasion}
Campaign: {strategy.strategy_title}
Campaign type: {(campaign_type or 'standard').replace('_', ' ')}
HERO product (the ONLY bottle shown, no other brands): {hero}
Customer-facing offer (exact price/discount — this is what the price shows): {customer_offer}
Target customers: {strategy.target_customer_segment}

CONFIRMED PRODUCT FACTS (use ONLY these; invent nothing else): {facts_txt}

{f"OWNER'S ART-DIRECTION BRIEF (the primary creative brief — follow it closely): {owner_hint}" if owner_hint else ""}
Composition preference for variety: {variety}.

Produce the structured design_plan + platform copy. Keep the headline ≤6 words and
product_details to at most 3 SHORT confirmed facts/benefits. Never invent facts;
never mention cost/margin/profit. Remember: direct the PHOTOGRAPH only — no text
layout, and no badges/stickers/ribbons/price-tags anywhere in the scene."""


# ─── Validation ────────────────────────────────────────────────────────────────

REQUIRED_FIELDS = {
    "design_plan",
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
    empty = [k for k in REQUIRED_FIELDS if k != "design_plan" and not data.get(k)]
    if empty:
        raise ValueError(f"OpenAI response has empty fields: {empty}")
    if not isinstance(data.get("design_plan"), dict):
        raise ValueError("OpenAI response missing a design_plan object")


# ─── Public service functions ──────────────────────────────────────────────────

async def generate_ad_creative(
    strategy_id: uuid.UUID,
    store_id: uuid.UUID,
    db: AsyncSession,
    offer_override: str | None = None,
    instructions: str | None = None,
    product_image_url: str | None = None,
    image_format: str = "square",
    product_facts: dict | None = None,
    campaign_type: str | None = None,
    show_product_details: bool = False,
    ad_layout: str | None = None,
) -> AdCreative:
    """
    Full pipeline: strategy → GPT-4o design plan (validated) → gpt-image-1 scene
    → deterministic Pillow text layer → DB.

    offer_override sets the EXACT promo price; instructions are the primary brief.
    product_facts (confirmed, owner-controlled) ground the plan — never invented.
    product_image_url (Phase 16): real product photo → accurate hero via edit.
    campaign_type / show_product_details gate whether customer-facing product
    details appear at all (otherwise the ad stays clean and minimal).

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

    logger.info("Generating ad creative for strategy=%s (offer_override=%s)",
                strategy_id, bool(offer_override))

    # 2. GPT-4o: structured design plan + platform copy
    ai_data = await generate_json_response(
        SYSTEM_PROMPT,
        _build_user_prompt(strategy, offer_override, instructions, product_facts, campaign_type),
    )
    _validate_creative(ai_data)

    hero_name = _choose_hero(strategy, offer_override)

    # Auto-use the hero product's saved library photo ("upload once, reuse forever")
    if not product_image_url and hero_name:
        from app.services.product_photo_service import get_photo_url
        product_image_url = await get_photo_url(store_id, str(hero_name), db)

    # Auto-use saved product facts if the caller didn't pass any this time
    if not product_facts and hero_name:
        from app.services.product_facts_service import get_facts
        product_facts = await get_facts(store_id, str(hero_name), db)

    # Map the chosen format to a gpt-image-1 size.
    #   square   1024x1024  → social posts
    #   portrait 1024x1536  → printable poster / A4-ish flyer
    #   landscape 1536x1024 → Facebook / banners
    size = {
        "square": "1024x1024",
        "portrait": "1024x1536",
        "landscape": "1536x1024",
    }.get(image_format, "1024x1024")

    # Validate the AI design plan deterministically, then compose the image prompt.
    from app.services import design_plan as dp
    hero = hero_name or "the promoted bottle"
    base_offer = offer_override.strip() if offer_override and offer_override.strip() else strategy.recommended_offer
    customer_offer = _strip_internal_numbers(base_offer)

    # What the POS says this bottle actually sells for. Used only to reject a
    # price that clearly belongs to a different product — never to invent one.
    known_price = await _known_unit_price(store_id, str(hero), db) if hero_name else None

    plan = dp.validate_design_plan(
        ai_data["design_plan"], str(hero), customer_offer, product_facts,
        campaign_type=campaign_type, owner_wants_details=show_product_details,
        promoted_products=list(strategy.products_to_promote or []),
        known_unit_price=known_price,
    )
    # The AI paints the SCENE + PRODUCT only: no text, no badges. Text is typeset
    # below by Pillow so it is never cropped and the price is always exact.
    image_prompt = dp.compose_image_prompt(plan, strategy.store_name)

    # 3. Generate the scene — real-photo edit path if a product photo is available
    if product_image_url:
        product_png = _to_png(await fetch_image(product_image_url))
        edit_prompt = (
            "Using the provided product photo as the EXACT hero bottle — preserve its "
            "real label, shape, and colors, do NOT redraw or rename the label. "
            + image_prompt
        )
        png_bytes = await generate_image_edit(prompt=edit_prompt, product_png=product_png, size=size)
    else:
        png_bytes = await generate_image(prompt=image_prompt, size=size)

    # 4. Typeset the deterministic ad text onto the scene → the FINISHED ad.
    #    Headline, exact price, store name (+ gated product details). Never badges.
    from app.services.ad_text_renderer import render_ad_text
    png_bytes = await render_ad_text(
        png_bytes, dp.ad_text_spec(plan, strategy.store_name), ad_layout
    )

    # 5. Persist image (local disk in dev, Cloudinary CDN in prod)
    image_url = await save_image(png_bytes, prefix="ad")
    logger.info("Finished ad saved: %s (%d KB)", image_url, len(png_bytes) // 1024)

    # 6. Save to DB
    creative = AdCreative(
        store_id=store_id,
        strategy_id=strategy_id,
        image_prompt=image_prompt,
        image_url=image_url,
        instagram_caption=ai_data["instagram_caption"],
        facebook_post=ai_data["facebook_post"],
        ubereats_description=ai_data["ubereats_description"],
        doordash_description=ai_data["doordash_description"],
        website_banner_headline=ai_data["website_banner_headline"],
        website_banner_text=ai_data["website_banner_text"],
        design_plan=plan,
        # design_json stays NULL here on purpose: label overlays belong to the
        # Label Studio, which creates its own LabelDesign row when opened.
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
