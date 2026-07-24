"""
services/strategy_service.py — AI promotion strategy 2.0 (Phase 15)

Rebuilt after real-owner feedback: "slowest item" was the wrong signal — the
long tail isn't what a store owner cares about. Real growth for a US liquor
store comes from:
  1. UPCOMING HOLIDAYS/EVENTS — the calendar drives alcohol sales.
  2. SUPPLIER DEAL BUYS — cheap closeout stock = high-margin promo weapons.
  3. LEANING INTO STRENGTH — top sellers & strong categories, not dead SKUs.
  4. OFFLINE + ONLINE — in-store tactics (where they struggle most) PLUS
     online listing copy (Vivino, social, delivery apps).

The engine assembles this context and asks GPT-4o for a complete campaign:
occasion, offer, products, offline plan, online plan, Vivino listing, and
ready-to-send SMS/email/social copy.
"""

import json
import logging
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_strategy_report import AIStrategyReport
from app.models.deal_buy import DealBuy
from app.models.store import Store
from app.services.analytics_service import (
    get_category_performance,
    get_slow_products,
    get_top_products,
)
from app.services.deal_service import list_deals
from app.services.holiday_calendar import get_upcoming_holidays
from app.services.openai_service import generate_json_response

logger = logging.getLogger(__name__)

# ─── Prompt ────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a growth strategist for independent US liquor stores.
You design practical, profitable promotion campaigns a small neighborhood store
can actually run — with a strong focus on OFFLINE / in-store execution, because
that's where these stores struggle and where most of their revenue is.

Principles:
  - Lead with the OCCASION or OPPORTUNITY (an upcoming US holiday, a supplier
    deal buy, or a clear growth angle) — not with random slow items.
  - When DEAL BUYS are provided, build the campaign around moving them: they're
    cheap, so you can discount aggressively and STILL make strong margin — state
    the margin. If SEVERAL deal buys are given (e.g. multiple closeout wines),
    BUNDLE them into one campaign: a mixed "closeout sale" table, a build-your-own
    case (e.g. any 6 for $X), or a BOGO / buy-one-get-one that still nets healthy
    margin because the cost basis is so low. Show the BOGO margin math.
  - Use the store's TOP SELLERS and strong categories to anchor bundles and
    cross-sells (people buy what they already come in for).
  - Offline tactics must be concrete: endcap/display placement, shelf-talkers,
    counter bundles, window signage, "ask at register" upsells, in-store tastings.
  - Online tactics: social posts, delivery-app (Uber Eats/DoorDash) features, and
    a Vivino-ready listing for any wine (rich tasting notes help it sell online).
  - Respect responsible alcohol marketing: never target minors, never encourage
    excessive drinking, keep it classy.

Respond with valid JSON matching EXACTLY this schema — no extra keys, no missing keys:
{
  "occasion": "string — what this campaign is built around",
  "strategy_type": "holiday | deal | growth",
  "strategy_title": "string — catchy campaign name",
  "products_to_promote": ["string", ...],
  "reason": "string — why this will grow revenue now",
  "target_customer_segment": "string — who to target",
  "recommended_offer": "string — the offer + note the margin if a deal buy is used",
  "offline_plan": "string — concrete in-store execution steps",
  "online_plan": "string — social + delivery-app tactics",
  "vivino_listing": "string — Vivino/online product listing copy (tasting notes, pairings); empty string if no wine involved",
  "sms_copy": "string — under 160 chars, no emojis",
  "email_subject": "string — compelling subject line",
  "email_body": "string — 2-3 sentence email body",
  "social_caption": "string — Instagram/Facebook caption with a few hashtags",
  "expected_impact": "string — realistic expected outcome"
}"""

REQUIRED_FIELDS = {
    "occasion", "strategy_type", "strategy_title", "products_to_promote", "reason",
    "target_customer_segment", "recommended_offer", "offline_plan", "online_plan",
    "vivino_listing", "sms_copy", "email_subject", "email_body", "social_caption",
    "expected_impact",
}


def _validate(data: dict) -> None:
    missing = REQUIRED_FIELDS - set(data.keys())
    if missing:
        raise ValueError(f"OpenAI response missing fields: {missing}")
    # vivino_listing may be empty; everything else must be non-empty
    empty = [k for k in REQUIRED_FIELDS if k != "vivino_listing" and not data.get(k)]
    if empty:
        raise ValueError(f"OpenAI response has empty fields: {empty}")


def _deal_context(deal: DealBuy) -> str:
    margin = ""
    if deal.normal_price and deal.cost_price:
        margin_pct = round((float(deal.normal_price) - float(deal.cost_price)) / float(deal.normal_price) * 100)
        margin = f" (normal ${deal.normal_price}, ~{margin_pct}% margin even at a discount)"
    qty = f", {deal.quantity} units to move" if deal.quantity else ""
    return f"{deal.product_name} — bought at ${deal.cost_price}/unit{margin}{qty}"


def _build_user_prompt(
    store_name: str,
    top_products: list[dict],
    categories: list[dict],
    deals: list[DealBuy],
    holidays: list[dict],
    slow_products: list[dict],
    focus_deals: list[DealBuy],
    occasion: str | None = None,
    instructions: str | None = None,
) -> str:
    parts = [f"Store: {store_name}", ""]

    # Owner-chosen event takes top priority (a specific holiday or a custom event)
    if occasion:
        parts += [f"PRIMARY FOCUS — build the campaign around this event: {occasion}."]
        match = next((h for h in holidays if occasion.lower() in h["name"].lower()), None)
        if match:
            parts.append(f"  ({match['name']} in {match['days_away']} days — {match['why']} Push: {match['push']})")
        if focus_deals:
            parts.append("  Also feature these deal buys in it:")
            parts += [f"    - {_deal_context(d)}" for d in focus_deals]
        parts.append("")
    elif focus_deals:
        if len(focus_deals) == 1:
            parts += ["PRIMARY FOCUS — build the campaign around this supplier deal buy:",
                      f"  {_deal_context(focus_deals[0])}", ""]
        else:
            parts += [f"PRIMARY FOCUS — BUNDLE these {len(focus_deals)} closeout deal buys "
                      "into ONE campaign (mixed sale / build-your-own case / BOGO with margin math):"]
            parts += [f"  - {_deal_context(d)}" for d in focus_deals]
            parts.append("")
    elif holidays:
        h = holidays[0]
        parts += [f"PRIMARY FOCUS — the next big event is {h['name']} in {h['days_away']} days.",
                  f"  Why it matters: {h['why']}",
                  f"  What sells: {h['push']}", ""]

    if holidays:
        parts.append("Upcoming US events (next ~45 days):")
        for h in holidays[:5]:
            parts.append(f"  - {h['name']} ({h['days_away']}d): {h['push']}")
        parts.append("")

    if deals:
        parts.append("Supplier deal buys available (cheap stock = high-margin promos):")
        for d in deals[:8]:
            parts.append(f"  - {_deal_context(d)}")
        parts.append("")

    if top_products:
        parts.append("Store's TOP SELLERS (anchor bundles/cross-sells on these strengths):")
        for p in top_products[:8]:
            parts.append(f"  - {p['product_name']} ({p.get('category') or 'n/a'}): ${p['total_revenue']} revenue")
        parts.append("")

    if categories:
        parts.append("Category performance:")
        for c in categories[:6]:
            parts.append(f"  - {c['category']}: ${c['total_revenue']} ({c['revenue_percentage']}%)")
        parts.append("")

    if slow_products:
        parts.append("Slow movers (only clear these if it fits the campaign — secondary):")
        for p in slow_products[:5]:
            parts.append(f"  - {p['product_name']}: ${p['total_revenue']} revenue")
        parts.append("")

    if instructions:
        parts += ["", "OWNER INSTRUCTIONS — follow these closely (they override defaults):",
                  f"  {instructions}", ""]

    parts.append(
        "Design ONE focused campaign. Be specific with real product names. Emphasize "
        "concrete OFFLINE in-store execution, and include online + Vivino copy. Make the "
        "offer realistic and profitable for a small store."
    )
    return "\n".join(parts)


# ─── Public API ────────────────────────────────────────────────────────────────

async def generate_promotion_strategy(
    store_id: uuid.UUID,
    db: AsyncSession,
    limit: int = 5,
    deal_ids: list[uuid.UUID] | None = None,
    occasion: str | None = None,
    instructions: str | None = None,
) -> AIStrategyReport:
    """
    Assemble rich context (top sellers, categories, deals, holidays, slow movers)
    and generate a complete occasion-aware campaign. If deal_ids are given, the
    campaign centers on those deal buys (several = a bundled closeout campaign).
    """
    result = await db.execute(select(Store).where(Store.id == store_id))
    store = result.scalar_one_or_none()
    if not store:
        raise ValueError("Store not found")

    top_products = await get_top_products(store_id=store_id, db=db, limit=10)
    categories = await get_category_performance(store_id=store_id, db=db)
    slow_products = await get_slow_products(store_id=store_id, db=db, limit=limit)
    deals = await list_deals(store_id=store_id, db=db)
    holidays = get_upcoming_holidays(date.today(), days=45)

    focus_deals: list[DealBuy] = []
    if deal_ids:
        wanted = set(deal_ids)
        focus_deals = [d for d in deals if d.id in wanted]
        if not focus_deals:
            raise ValueError("Deal buy not found")

    if not (top_products or deals or holidays):
        raise ValueError(
            "Not enough context yet. Upload a sales report, add a deal buy, "
            "or wait for an upcoming event."
        )

    logger.info("Strategy 2.0 for store=%s (focus_deals=%d, %d holidays, %d deals)",
                store_id, len(focus_deals), len(holidays), len(deals))

    user_prompt = _build_user_prompt(
        store.name, top_products, categories, deals, holidays, slow_products, focus_deals,
        occasion=(occasion or "").strip() or None,
        instructions=(instructions or "").strip() or None,
    )
    ai_data = await generate_json_response(SYSTEM_PROMPT, user_prompt)
    _validate(ai_data)

    report = AIStrategyReport(
        store_id=store_id,
        store_name=store.name,
        products_analyzed={"top_products": top_products, "deals": [d.product_name for d in deals]},
        strategy_title=ai_data["strategy_title"],
        products_to_promote=ai_data["products_to_promote"],
        reason=ai_data["reason"],
        target_customer_segment=ai_data["target_customer_segment"],
        recommended_offer=ai_data["recommended_offer"],
        sms_copy=ai_data["sms_copy"],
        email_subject=ai_data["email_subject"],
        email_body=ai_data["email_body"],
        social_caption=ai_data["social_caption"],
        expected_impact=ai_data["expected_impact"],
        occasion=ai_data["occasion"],
        strategy_type=ai_data["strategy_type"],
        offline_plan=ai_data["offline_plan"],
        online_plan=ai_data["online_plan"],
        vivino_listing=ai_data.get("vivino_listing") or None,
        model_used=str(ai_data.get("model_used", "gpt-4o")),
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    logger.info("Strategy 2.0 saved: id=%s occasion=%s", report.id, report.occasion)
    return report


async def get_all_strategies(store_id: uuid.UUID, db: AsyncSession) -> list[AIStrategyReport]:
    result = await db.execute(
        select(AIStrategyReport)
        .where(AIStrategyReport.store_id == store_id)
        .order_by(AIStrategyReport.created_at.desc())
    )
    return list(result.scalars().all())


async def get_strategy_by_id(
    strategy_id: uuid.UUID, store_id: uuid.UUID, db: AsyncSession,
) -> AIStrategyReport | None:
    result = await db.execute(
        select(AIStrategyReport).where(
            AIStrategyReport.id == strategy_id,
            AIStrategyReport.store_id == store_id,
        )
    )
    return result.scalar_one_or_none()
