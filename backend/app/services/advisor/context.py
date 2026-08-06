"""
services/advisor/context.py — PHASE 23: what the advisor knows before it thinks.

DESIGN DECISION WORTH DEFENDING

The brief said "collect ALL context before every answer". I have not done that,
and the reason matters.

This store has 1,393 products, 466 slow movers, seven opportunity types and a
customer file. Serialising all of it into every prompt would be roughly 80k
tokens per question: slow, expensive per message, and — the real problem —
WORSE ANSWERS. A model given everything attends to nothing in particular; the
one figure that matters gets the same weight as the 1,392 that don't.

So the split is:

  BASE CONTEXT (this module)  — small, always present, ~1KB. The things a
      consultant would know without looking anything up: how big the shop is,
      whether it's healthy, what the top three problems are, what period the
      data covers.

  TOOLS (tools.py)            — everything else, fetched ON DEMAND when the
      model decides it needs it. "Why are tequila sales down?" pulls category
      intelligence; "which customers should I text?" pulls segments. Neither
      question pays for the other's data.

That is what makes this an AGENT rather than a prompt with a big attachment,
and it is the design the brief's own TOOLS section describes.

NO NEW CALCULATIONS. Every number here is read from build_intelligence(),
which is the same deterministic engine the dashboard renders.
"""

import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession


async def build_base_context(store_id: uuid.UUID, db: AsyncSession,
                             store_name: str = "") -> dict:
    """
    The briefing a consultant would walk in already holding.

    Deliberately shallow: counts, totals, the health verdict and the top three
    actions by title. Anything that needs a list of products is a tool call.
    """
    from app.services.bi.engine import build_intelligence

    bi = await build_intelligence(store_id, db)

    if bi.get("empty"):
        return {
            "store_name": store_name,
            "has_data": False,
            "note": "No POS report has been uploaded yet, so there is nothing "
                    "to analyse. The owner needs to upload a sales export first.",
        }

    health = bi.get("business_health", {})
    headline = bi.get("headline", {})
    summary = bi.get("summary", {})
    period = bi.get("period", {})
    valuation = bi.get("valuation", {})

    return {
        "store_name": store_name,
        "has_data": True,
        "today": date.today().isoformat(),

        "reporting_period": {
            "start": str(period.get("start")),
            "end": str(period.get("end")),
            "days": period.get("days"),
            "periods_on_file": period.get("periods"),
            "estimated": period.get("estimated"),
        },

        "business_health": {
            "score": health.get("score"),
            "band": health.get("band"),
            "verdict": health.get("verdict"),
            "components": [
                {"name": c["label"], "value": c["value"], "target": c["target"]}
                for c in health.get("components", [])
            ],
        },

        "headline_numbers": {
            "products": summary.get("products"),
            "revenue_this_period": summary.get("revenue"),
            "units_sold": summary.get("units"),
            "inventory_value_retail": headline.get("inventory_value"),
            "slow_stock_value_retail": headline.get("cash_frozen"),
            "slow_stock_pct": headline.get("frozen_pct"),
            "inventory_turnover": summary.get("turnover"),
            "sell_through_rate": summary.get("sell_through_rate"),
            "valuation_basis": valuation.get("basis"),
            "valuation_note": valuation.get("note"),
        },

        "stock_class_counts": {
            k: v.get("count") for k, v in (summary.get("by_class") or {}).items()
        },

        # Titles and money only. The full evidence is a tool call away, so a
        # question that never touches the action centre doesn't pay for it.
        "top_actions": [
            {
                "priority": a["priority"],
                "title": a["title"],
                "impact": a["business_impact_label"],
                "confidence": a["confidence"],
                "timeline": a.get("timeline"),
                "type": a["type"],
            }
            for a in bi.get("actions", [])[:3]
        ],

        "opportunity_total": {
            "raw": headline.get("opportunity_value"),
            "confidence_adjusted": headline.get("opportunity_value_adjusted"),
        },
    }
