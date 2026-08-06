"""
services/advisor/tools.py — PHASE 23: what the advisor can look up.

Every tool is a thin adapter over a service that already exists. NOTHING HERE
CALCULATES ANYTHING. If a tool did its own arithmetic there would be two
sources of truth for the same figure, and the advisor would eventually
contradict the dashboard — which is the fastest way to lose a shop owner's
trust in both.

WHY TOOLS INSTEAD OF ONE BIG PROMPT

"Why are tequila sales down?" needs category intelligence.
"Which customers should I text?" needs RFM segments.
Neither needs the other. Loading both every time costs money and dilutes the
model's attention across data it has no use for.

Letting the model choose also produces the explainability the brief asks for:
the tools it called ARE the citation list. We don't have to ask it which data
it used — we watched.

CONTRACT FOR EVERY TOOL
  · async, takes (store_id, db, **args), returns a JSON-serialisable dict
  · never raises: a failure returns {"error": ...} so the agent can say
    "I don't have that" instead of the whole request collapsing
  · returns SHAPED, TRIMMED output — a 1,393-row dump helps nobody
"""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# How many rows any single tool may return. The model reasons about patterns,
# not about row 700, and an unbounded list is how a context window dies.
MAX_ROWS = 25


# ── The implementations ──────────────────────────────────────────────────────

async def inventory_intelligence(store_id, db, stock_class: str = None,
                                 category: str = None, limit: int = MAX_ROWS):
    """Product-level stock health, optionally filtered."""
    from app.services.bi.engine import build_intelligence

    bi = await build_intelligence(store_id, db)
    rows = bi.get("products", [])
    if stock_class:
        rows = [p for p in rows if p["stock_class"] == stock_class]
    if category:
        rows = [p for p in rows if (p.get("category") or "").lower() == category.lower()]

    # RANKED BEFORE IT REACHES THE MODEL. "You have 466 slow products" is not
    # advice; the ten holding the most money is. Sorting an existing figure is
    # presentation, not calculation — the values are the engine's.
    if stock_class in ("sold_out", "critical", "reorder"):
        rows = sorted(rows, key=lambda p: -(p.get("money_at_stake") or 0))
        ranked_by = "money at risk from being out of stock (highest first)"
    elif stock_class in ("sleeping", "overstock", "dead"):
        rows = sorted(rows, key=lambda p: -(p.get("cash_frozen") or 0))
        ranked_by = "retail value of stock sitting still (highest first)"
    else:
        rows = sorted(rows, key=lambda p: -(p.get("opportunity_score") or 0))
        ranked_by = "opportunity score (highest first)"

    return {
        "matching_products": len(rows),
        "ranked_by": ranked_by,
        "showing": f"top {min(limit, MAX_ROWS)} of {len(rows)}",
        "class_totals": bi.get("summary", {}).get("by_class", {}),
        "products": [
            {k: p[k] for k in ("product_name", "category", "stock_class", "stock",
                               "units_sold", "weeks_of_supply", "unit_price",
                               "inventory_value", "cash_frozen")}
            for p in rows[:min(limit, MAX_ROWS)]
        ],
    }


async def category_intelligence(store_id, db):
    """Per-category revenue, inventory, money stuck and mover counts."""
    from app.services.bi.engine import build_intelligence

    bi = await build_intelligence(store_id, db)
    # Already sorted by cash frozen in the engine — stated explicitly so the
    # model presents them in a meaningful order rather than alphabetically.
    return {
        "ranked_by": "retail value of stock sitting still (worst first)",
        "categories": bi.get("categories", [])[:MAX_ROWS],
        "coverage": bi.get("coverage", {}),
    }


async def action_center(store_id, db):
    """Every ranked recommendation, with evidence, timeline and confidence."""
    from app.services.bi.engine import build_intelligence

    bi = await build_intelligence(store_id, db)
    return {
        "actions": [
            {k: a.get(k) for k in ("priority", "type", "title", "business_impact",
                                   "business_impact_label", "confidence",
                                   "confidence_reason", "evidence",
                                   "expected_outcome", "suggested_action",
                                   "timeline", "timeline_reason", "estimated",
                                   "products", "allocation_note")}
            for a in bi.get("actions", [])
        ],
        "assumptions": bi.get("assumptions", []),
    }


async def reorder_list(store_id, db, horizon_weeks: float = 4.0):
    """What to buy and how many, net of stock already on hand."""
    from app.services.bi import reorder as REORDER
    from app.services.bi.engine import build_intelligence

    bi = await build_intelligence(store_id, db)
    rows = REORDER.build_reorder_list(bi.get("products", []), horizon_weeks)
    return {
        "totals": REORDER.summarise(rows, horizon_weeks),
        "items": rows[:MAX_ROWS],
        "note": "Values are RETAIL, not cost — the POS export has no cost data.",
    }


async def customer_segments(store_id, db):
    """RFM segments: who is loyal, who is lapsing, who is gone."""
    from app.services.customer_service import segment_summary

    data = await segment_summary(store_id, db)
    return {
        "total_customers": data.get("total_customers"),
        "total_value": data.get("total_value"),
        "sms_opted_in": data.get("sms_opted_in"),
        "email_opted_in": data.get("email_opted_in"),
        "segments": data.get("segments"),
    }


async def campaign_performance(store_id, db):
    """Measured lift from campaigns already run."""
    from app.models.ai_strategy_report import AIStrategyReport
    from app.services.campaign_service import get_campaign_performance

    strategies = list((await db.execute(
        select(AIStrategyReport)
        .where(AIStrategyReport.store_id == store_id)
        .order_by(AIStrategyReport.created_at.desc())
        .limit(10)
    )).scalars().all())

    out = []
    for s in strategies:
        try:
            perf = await get_campaign_performance(s.id, store_id, db)
        except Exception:  # noqa: BLE001 — one bad campaign must not sink the tool
            continue
        out.append({
            "title": s.strategy_title,
            "created_at": str(s.created_at),
            "status": perf.get("status"),
            "days_elapsed": perf.get("days_elapsed"),
            "revenue_lift": perf.get("total_revenue_lift"),
            "units_lift_pct": perf.get("total_units_lift_pct"),
        })
    return {"campaigns": out, "measured": len(out)}


async def ai_strategies(store_id, db, limit: int = 5):
    """Campaigns the owner has already been given, so we don't repeat them."""
    from app.models.ai_strategy_report import AIStrategyReport

    rows = list((await db.execute(
        select(AIStrategyReport)
        .where(AIStrategyReport.store_id == store_id)
        .order_by(AIStrategyReport.created_at.desc())
        .limit(min(limit, 10))
    )).scalars().all())

    return {"strategies": [
        {
            # The ID is what makes a recommendation actionable: without it the
            # "Create ad" button can only open a blank Ad Creator and ask the
            # owner to re-pick the strategy the advisor just named.
            "id": str(s.id),
            "title": s.strategy_title,
            "created_at": str(s.created_at),
            "occasion": s.occasion,
            "target_segment": s.target_segment,
            "products": s.products_to_promote,
            "offer": s.recommended_offer,
            "expected_impact": s.expected_impact,
        }
        for s in rows
    ]}


async def upcoming_holidays(store_id, db, days: int = 60):
    """Drinking holidays inside the planning window, and what sells for each."""
    from app.services.bi import seasonality as SEASON
    from app.services.holiday_calendar import get_upcoming_holidays

    events = get_upcoming_holidays(days=min(days, 120))
    return {"holidays": [
        {
            "name": e["name"],
            "date": str(e["date"]),
            "days_away": e["days_away"],
            "why": e.get("why"),
            "relevant_categories": SEASON.rule_for(e["key"])["categories"],
            "assumed_lift": SEASON.rule_for(e["key"])["lift"],
        }
        for e in events
    ]}


async def supplier_deals(store_id, db):
    """Deal buys the owner has recorded — the ones he's deciding about."""
    from app.services.deal_service import list_deals

    deals = await list_deals(store_id, db, active_only=False)
    return {"deals": [
        {
            "product_name": getattr(d, "product_name", None),
            "supplier": getattr(d, "supplier", None),
            "unit_cost": float(getattr(d, "unit_cost", 0) or 0),
            "quantity": getattr(d, "quantity", None),
            "expires_on": str(getattr(d, "expires_on", "") or ""),
            "is_active": getattr(d, "is_active", None),
            "notes": getattr(d, "notes", None),
        }
        for d in deals[:MAX_ROWS]
    ]}


async def revenue_trend(store_id, db):
    """Revenue per reporting period, oldest first."""
    from app.services.analytics_service import get_sales_trend

    points = await get_sales_trend(store_id, db)
    return {
        "periods": len(points),
        "trend": points[-12:],
        "note": ("Fewer than 4 periods on file — this is a snapshot, not a trend."
                 if len(points) < 4 else "Enough history to read a direction."),
    }


async def product_lookup(store_id, db, query: str, limit: int = 10):
    """One product, or a handful matching a name — for specific questions."""
    from app.services.bi.engine import build_intelligence

    bi = await build_intelligence(store_id, db)
    needle = (query or "").lower().strip()
    if not needle:
        return {"error": "No product name given."}

    hits = [p for p in bi.get("products", [])
            if needle in (p.get("product_name") or "").lower()]
    hits = sorted(hits, key=lambda p: -(p.get("inventory_value") or 0))
    return {
        "query": query,
        "matches": len(hits),
        "ranked_by": "retail value on hand (highest first)",
        "products": hits[:min(limit, MAX_ROWS)],
    }


# ── The registry the model sees ──────────────────────────────────────────────

REGISTRY = {
    "inventory_intelligence": {
        "fn": inventory_intelligence,
        "description": (
            "Product-level stock health: what is sold out, running low, "
            "overstocked, sleeping or dead, with weeks of supply and retail "
            "value. Filter by stock_class or category. Use for questions about "
            "what to reorder, what is not selling, or where cash is stuck."
        ),
        "parameters": {
            "stock_class": {"type": "string", "description":
                "One of: sold_out, critical, reorder, healthy, heavy, "
                "overstock, sleeping, dead, negative"},
            "category": {"type": "string", "description":
                "e.g. Tequila, Wine, Beer. Omit for all categories."},
            "limit": {"type": "integer", "description": "Max products, default 25"},
        },
    },
    "category_intelligence": {
        "fn": category_intelligence,
        "description": (
            "Revenue, inventory value, money stuck, fast/slow mover counts and "
            "frozen share for every product category. Use for 'why are tequila "
            "sales down' or 'which category needs attention'."
        ),
        "parameters": {},
    },
    "action_center": {
        "fn": action_center,
        "description": (
            "Every ranked recommendation with its evidence, expected outcome, "
            "confidence, reasoning and execution timeline, plus the engine's "
            "assumptions. Use for 'what should I do', 'what is my priority', "
            "'where am I losing money'."
        ),
        "parameters": {},
    },
    "reorder_list": {
        "fn": reorder_list,
        "description": (
            "A purchase list: which products to buy and how many, net of stock "
            "already on hand, for a given horizon in weeks. Use for 'what "
            "should I reorder first'."
        ),
        "parameters": {
            "horizon_weeks": {"type": "number", "description":
                "Weeks of demand to cover, default 4"},
        },
    },
    "customer_segments": {
        "fn": customer_segments,
        "description": (
            "RFM customer segments — VIP, High Value, Loyal, New, At Risk, "
            "Inactive, Regular — with counts and spend, plus SMS/email opt-in "
            "numbers. Use for retention, win-back and 'who should I text'."
        ),
        "parameters": {},
    },
    "campaign_performance": {
        "fn": campaign_performance,
        "description": (
            "Measured revenue lift from campaigns already run, comparing the "
            "weeks after against the weeks before. Use for ROI questions and "
            "'did my last campaign work'."
        ),
        "parameters": {},
    },
    "ai_strategies": {
        "fn": ai_strategies,
        "description": (
            "Campaigns previously generated for this store — titles, products, "
            "offers, occasions. Use to avoid recommending something the owner "
            "was already given, or to suggest repeating one that worked."
        ),
        "parameters": {"limit": {"type": "integer", "description": "Default 5"}},
    },
    "upcoming_holidays": {
        "fn": upcoming_holidays,
        "description": (
            "US drinking holidays in the planning window, with the categories "
            "that actually sell for each and the assumed lift. Use for "
            "seasonal planning."
        ),
        "parameters": {"days": {"type": "integer", "description": "Window, default 60"}},
    },
    "supplier_deals": {
        "fn": supplier_deals,
        "description": (
            "Deal buys the owner has recorded: product, supplier, unit cost, "
            "quantity, expiry. Use for 'should I take this deal'."
        ),
        "parameters": {},
    },
    "revenue_trend": {
        "fn": revenue_trend,
        "description": (
            "Revenue per reporting period, oldest first. Says explicitly when "
            "there are too few periods to read a direction. Use for 'are sales "
            "up or down', 'how was last month', or any question about whether "
            "something is getting better or worse over time."
        ),
        "parameters": {},
    },
    "product_lookup": {
        "fn": product_lookup,
        "description": (
            "Find one product or a few by name, with full stock metrics. Use "
            "when the owner names a specific bottle."
        ),
        "parameters": {
            "query": {"type": "string", "description": "Part of the product name"},
            "limit": {"type": "integer", "description": "Default 10"},
        },
    },
}


def openai_schema() -> list[dict]:
    """The registry, in the shape the Chat Completions API wants."""
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": spec["description"],
                "parameters": {
                    "type": "object",
                    "properties": spec["parameters"],
                    "required": [],
                },
            },
        }
        for name, spec in REGISTRY.items()
    ]


async def execute(name: str, args: dict, store_id: uuid.UUID,
                  db: AsyncSession) -> dict:
    """
    Run one tool. Never raises.

    A tool that blows up must degrade to "I couldn't look that up" rather than
    failing the whole conversation — the owner asked a question and deserves an
    answer about the parts that did work.
    """
    spec = REGISTRY.get(name)
    if not spec:
        return {"error": f"No such tool: {name}"}
    try:
        return await spec["fn"](store_id, db, **(args or {}))
    except TypeError as exc:
        logger.warning("Advisor tool %s called with bad arguments: %s", name, exc)
        return {"error": f"Invalid arguments for {name}: {exc}"}
    except Exception as exc:  # noqa: BLE001 — see docstring
        logger.warning("Advisor tool %s failed", name, exc_info=True)
        return {"error": f"Could not load {name}: {exc}"}
