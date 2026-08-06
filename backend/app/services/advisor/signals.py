"""
services/advisor/signals.py — PHASE 23.5: unusual situations, found for you.

A briefing that says "your health score is 39" every morning is wallpaper. What
a consultant actually opens with is what CHANGED, or what is about to run out
of time: a deal expiring on Friday, a report that hasn't been uploaded in three
weeks, forty bottles that haven't moved in a year.

WHY THIS IS CODE AND NOT PROMPT INSTRUCTIONS

"Notice anything unusual" asked of a language model is an invitation to invent
something interesting. Detection has to be deterministic or it cannot be
trusted — the model is given the signals and explains them, exactly as in
Phase 22.

NO NEW METRICS. Every signal is a comparison or a date arithmetic over figures
the engine already produced. Nothing here computes a business number.
"""

import logging
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# A report older than this and the advice is being given about a shop that has
# since moved on. Three weeks is roughly when a monthly cadence has slipped.
STALE_UPLOAD_DAYS = 21

# A deal inside this window is a decision the owner has to make NOW.
DEAL_URGENT_DAYS = 14

# Enough sleeping products that it is a policy problem, not a few bad bets.
SLEEPING_ALARM = 25


async def detect(store_id: uuid.UUID, db: AsyncSession, base_context: dict,
                 today: date | None = None) -> list[dict]:
    """
    The things worth leading a briefing with, most urgent first.

    Each signal carries `urgency` (1 = act today) so the caller can order them,
    and `basis` so the advisor can say whether it is measured or a deadline.
    Never raises: a missing signal is a quieter briefing, not a failed one.
    """
    today = today or date.today()
    out: list[dict] = []

    if not base_context.get("has_data"):
        return out

    # ── The data itself is going stale ───────────────────────────────────────
    try:
        period = base_context.get("reporting_period") or {}
        end = period.get("end")
        if end and end != "None":
            days = (today - date.fromisoformat(str(end))).days
            if days >= STALE_UPLOAD_DAYS:
                out.append({
                    "urgency": 2,
                    "kind": "stale_data",
                    "headline": f"Your most recent report ends {days} days ago",
                    "detail": (
                        f"Everything I'm telling you describes the period to {end}. "
                        f"Stock levels have moved since then, so treat the reorder "
                        f"list as a starting point rather than gospel."
                    ),
                    "basis": "measured",
                })
    except Exception:  # noqa: BLE001
        logger.warning("Could not evaluate upload freshness", exc_info=True)

    # ── A supplier deal is about to expire ───────────────────────────────────
    try:
        from app.services.deal_service import list_deals

        for deal in await list_deals(store_id, db, active_only=True):
            expires = getattr(deal, "expires_on", None)
            if not expires:
                continue
            days = (expires - today).days
            if 0 <= days <= DEAL_URGENT_DAYS:
                name = getattr(deal, "product_name", "A supplier deal")
                out.append({
                    "urgency": 1 if days <= 5 else 2,
                    "kind": "deal_expiring",
                    "headline": (f"{name} deal expires in {days} day"
                                 f"{'' if days == 1 else 's'}"),
                    "detail": (
                        f"Decide before {expires}. A quantity deal is only worth "
                        f"taking if the product already sells — otherwise it buys "
                        f"more of a problem you already have."
                    ),
                    "basis": "measured",
                })
    except Exception:  # noqa: BLE001 — deals are optional
        logger.warning("Could not evaluate supplier deals", exc_info=True)

    # ── Products that have not moved in over a year ──────────────────────────
    counts = base_context.get("stock_class_counts") or {}
    sleeping = counts.get("sleeping") or 0
    if sleeping >= SLEEPING_ALARM:
        out.append({
            "urgency": 3,
            "kind": "sleeping_stock",
            "headline": f"{sleeping} products hold over a year of stock",
            "detail": (
                "At the current rate these will still be on the shelf next "
                "summer. This is a buying-pattern problem as much as a "
                "clearance one."
            ),
            "basis": "measured",
        })

    # ── Selling something you cannot supply ──────────────────────────────────
    sold_out = counts.get("sold_out") or 0
    if sold_out:
        out.append({
            "urgency": 1,
            "kind": "stock_outs",
            "headline": f"{sold_out} products that were selling are out of stock",
            "detail": (
                "Every day one of these is off the shelf is a sale that goes "
                "to whoever is open down the road. It does not come back later."
            ),
            "basis": "measured",
        })

    # ── A holiday close enough to need ordering NOW ──────────────────────────
    try:
        from app.services.holiday_calendar import get_upcoming_holidays

        for event in get_upcoming_holidays(today=today, days=35)[:1]:
            days = event["days_away"]
            out.append({
                "urgency": 2 if days <= 21 else 3,
                "kind": "holiday",
                "headline": f"{event['name']} is {days} days away",
                "detail": (
                    f"{event.get('why', '')} Ordering and pricing need to happen "
                    f"in the next {max(days - 7, 0)} days to have stock on the "
                    f"shelf in time."
                ).strip(),
                "basis": "measured",
            })
    except Exception:  # noqa: BLE001
        logger.warning("Could not evaluate the holiday calendar", exc_info=True)

    out.sort(key=lambda s: s["urgency"])
    return out[:4]
