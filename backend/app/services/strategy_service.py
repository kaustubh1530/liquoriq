"""
services/strategy_service.py — AI promotion strategy orchestration

This is the core of Phase 7. It:
  1. Pulls the store's slow-moving products from analytics_service
  2. Builds a detailed prompt with the real product data
  3. Calls OpenAI via openai_service and gets back a structured JSON strategy
  4. Validates every expected field is present in the response
  5. Saves the full strategy to ai_strategy_reports
  6. Returns the saved ORM object to the route layer

Why save to DB instead of returning directly?
  - The store owner can view all past strategies (GET /ai/strategies)
  - We avoid re-calling OpenAI if the user refreshes the page
  - We have an audit trail for every strategy ever generated
"""

import json
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.ai_strategy_report import AIStrategyReport
from app.models.store import Store
from app.services.analytics_service import get_slow_products
from app.services.openai_service import generate_json_response

logger = logging.getLogger(__name__)

# ─── Prompt templates ──────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a retail growth strategist specializing in independent
liquor stores. You generate practical, actionable promotion campaigns based on
sales data.

Always respond with valid JSON matching EXACTLY this schema — no extra keys,
no missing keys:
{
  "strategy_title": "string — catchy campaign name",
  "products_to_promote": ["string", ...],
  "reason": "string — why these products need promotion",
  "target_customer_segment": "string — who to target",
  "recommended_offer": "string — discount or bundle mechanic",
  "sms_copy": "string — under 160 chars, no emojis",
  "email_subject": "string — compelling email subject line",
  "email_body": "string — 2-3 sentence email body",
  "social_caption": "string — Instagram/Facebook caption",
  "expected_impact": "string — realistic expected business outcome"
}"""


def _build_user_prompt(store_name: str, products: list[dict]) -> str:
    """
    Convert real sales data into a specific, grounded prompt.
    Injecting actual numbers (revenue, units sold) anchors the AI
    to reality instead of generating generic advice.
    """
    products_text = json.dumps(products, indent=2)
    return f"""Store: {store_name}

The following products have the LOWEST sales revenue recently.
They need a promotion to move inventory and improve sales velocity.

Slow-moving products (with sales data):
{products_text}

Generate a promotion strategy campaign. Be specific — use the actual product
names in your response. The offer should be realistic for a small liquor store
(percentage discount, buy-one-get-one, bundle, etc.)."""


# ─── Required fields validation ────────────────────────────────────────────────

REQUIRED_FIELDS = {
    "strategy_title",
    "products_to_promote",
    "reason",
    "target_customer_segment",
    "recommended_offer",
    "sms_copy",
    "email_subject",
    "email_body",
    "social_caption",
    "expected_impact",
}


def _validate_strategy(data: dict) -> None:
    """Raise ValueError if any required field is missing or empty."""
    missing = REQUIRED_FIELDS - set(data.keys())
    if missing:
        raise ValueError(f"OpenAI response missing fields: {missing}")
    empty = [k for k in REQUIRED_FIELDS if not data.get(k)]
    if empty:
        raise ValueError(f"OpenAI response has empty fields: {empty}")


# ─── Public service functions ──────────────────────────────────────────────────

async def generate_promotion_strategy(
    store_id: uuid.UUID,
    db: AsyncSession,
    limit: int = 5,
) -> AIStrategyReport:
    """
    Full pipeline: fetch slow products → build prompt → call AI → save to DB.

    Args:
        store_id: The store requesting the strategy (from JWT)
        db:       Async DB session
        limit:    How many slow products to send to the AI (default 5)

    Returns:
        The saved AIStrategyReport ORM object

    Raises:
        ValueError  — if no sales data exists yet, or AI returns bad JSON
        RuntimeError — if OpenAI API fails
    """
    # 1. Fetch store name
    result = await db.execute(select(Store).where(Store.id == store_id))
    store = result.scalar_one_or_none()
    if not store:
        raise ValueError("Store not found")

    # 2. Get slow-moving products
    slow_products = await get_slow_products(store_id=store_id, db=db, limit=limit)
    if not slow_products:
        raise ValueError(
            "No sales data found. Upload and parse at least one report first."
        )

    logger.info(
        "Generating strategy for store=%s with %d products",
        store_id,
        len(slow_products),
    )

    # 3. Build prompts and call OpenAI
    system_prompt = SYSTEM_PROMPT
    user_prompt = _build_user_prompt(
        store_name=store.name,
        products=slow_products,
    )
    ai_data = await generate_json_response(system_prompt, user_prompt)

    # 4. Validate the response
    _validate_strategy(ai_data)

    # 5. Save to database
    report = AIStrategyReport(
        store_id=store_id,
        store_name=store.name,
        products_analyzed=slow_products,
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
        model_used=str(ai_data.get("model_used", "gpt-4o")),
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    logger.info("Strategy saved: id=%s title=%s", report.id, report.strategy_title)
    return report


async def get_all_strategies(
    store_id: uuid.UUID,
    db: AsyncSession,
) -> list[AIStrategyReport]:
    """Return all past strategies for this store, newest first."""
    result = await db.execute(
        select(AIStrategyReport)
        .where(AIStrategyReport.store_id == store_id)
        .order_by(AIStrategyReport.created_at.desc())
    )
    return list(result.scalars().all())


async def get_strategy_by_id(
    strategy_id: uuid.UUID,
    store_id: uuid.UUID,
    db: AsyncSession,
) -> AIStrategyReport | None:
    """Return a single strategy, ensuring it belongs to this store."""
    result = await db.execute(
        select(AIStrategyReport).where(
            AIStrategyReport.id == strategy_id,
            AIStrategyReport.store_id == store_id,
        )
    )
    return result.scalar_one_or_none()