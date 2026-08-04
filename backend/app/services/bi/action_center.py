"""
services/bi/action_center.py — PHASE 22: EXECUTIVE ACTION CENTER

Turns ranked opportunities into a short list of executive actions, and scores
the whole business in one number.

Every action carries the seven fields the brief requires:
    priority · business_impact · evidence · expected_outcome ·
    confidence · suggested_action · action (a real button)

All of it is deterministic. GPT is never consulted here — explain.py may add a
sentence of prose afterwards, and if it can't, nothing is lost.
"""

from app.services.bi import assumptions as A

# Priority bands. Urgency beats size: a stock-out bleeds money every day it
# stands, while frozen cash has already been sitting there for months.
URGENT_TYPES = {"reorder"}
TIME_BOXED_TYPES = {"seasonal", "campaign_repeat"}

PRIORITY_LABELS = {
    "P1": "Do this now",
    "P2": "This week",
    "P3": "When you get to it",
}


def _priority(opportunity, biggest_value: float) -> str:
    """
    P1 = urgent OR very large. P2 = time-boxed or materially large.
    P3 = everything else worth listing.
    """
    kind = opportunity["type"]
    value = opportunity["ranked_value"]
    share = (value / biggest_value) if biggest_value > 0 else 0.0

    if kind in URGENT_TYPES or share >= 0.5:
        return "P1"
    if kind in TIME_BOXED_TYPES or share >= 0.15:
        return "P2"
    return "P3"


def build_actions(opportunities, biggest_value=None) -> list[dict]:
    """One executive action per opportunity, in priority then value order."""
    if not opportunities:
        return []
    biggest = biggest_value or max((o["ranked_value"] for o in opportunities), default=0.0)

    actions = []
    for opportunity in opportunities:
        priority = _priority(opportunity, biggest)
        actions.append({
            "id": opportunity["type"],
            "priority": priority,
            "priority_label": PRIORITY_LABELS[priority],
            "title": opportunity["title"],
            # The money line the owner reads first.
            "business_impact": round(opportunity["value_score"], 2),
            "business_impact_label": f"${opportunity['value_score']:,.0f}",
            "ranked_value": opportunity["ranked_value"],
            # Always visible, never hidden behind a tooltip: this is what makes
            # the recommendation checkable rather than a black box.
            "evidence": opportunity["evidence"],
            "expected_outcome": opportunity["expected_outcome"],
            "confidence": opportunity["confidence"],
            "confidence_reason": opportunity["confidence_reason"],
            "suggested_action": opportunity["suggested_action"],
            "action": {
                "label": opportunity["suggested_action"],
                "route": opportunity["route"],
            },
            "products": opportunity.get("products", []),
            "type": opportunity["type"],
            # When to do it, and over how long. A recommendation with no
            # timeframe isn't a plan — "$132,396, do this now" was two months
            # of the store's entire revenue.
            "timeline": opportunity.get("timeline"),
            "timeline_reason": opportunity.get("timeline_reason"),
            "plan": opportunity.get("plan"),
            # Whether the money figure rests on an assumed rate.
            "estimated": opportunity.get("estimated", True),
            # Disclosed when products moved to a higher-value action, so the
            # owner can see why this number is smaller than the raw finding.
            "allocation_note": opportunity.get("allocation_note"),
            "products_yielded": opportunity.get("products_yielded", 0),
        })

    order = {"P1": 0, "P2": 1, "P3": 2}
    actions.sort(key=lambda a: (order[a["priority"]], -a["ranked_value"]))
    return actions


# ── Business health score ────────────────────────────────────────────────────

def _turnover_component(turnover) -> float:
    """0-1 against the 4–6x benchmark. Above the top of the band scores full."""
    if not turnover or turnover <= 0:
        return 0.0
    if turnover >= A.TURNOVER_BENCHMARK_HIGH:
        return 1.0
    if turnover <= 0.5:
        return 0.0
    return min(turnover / A.TURNOVER_BENCHMARK_HIGH, 1.0)


def business_health(summary: dict, metrics: list[dict]) -> dict:
    """
    One number for the whole store, so the owner can watch it move instead of
    reading nine tables. Every component is shown alongside it — a score with
    no visible parts is just a horoscope.
    """
    total_value = summary.get("inventory_value") or 0.0
    products = summary.get("products") or 0

    healthy_cash = sum(m["inventory_value"] for m in metrics
                       if m["stock_class"] in ("healthy", "reorder", "critical"))
    healthy_share = (healthy_cash / total_value) if total_value > 0 else 0.0

    sold_out = sum(1 for m in metrics if m["stock_class"] == "sold_out")
    negative = sum(1 for m in metrics if m["stock_class"] == "negative")
    uncategorised = sum(1 for m in metrics if (m.get("category") or "Other") == "Other")

    availability = 1.0 - (sold_out / products) if products else 0.0
    data_quality = 1.0 - ((negative + uncategorised) / products) if products else 0.0
    sell_through = min(summary.get("sell_through_rate") or 0.0, 1.0)
    turnover_component = _turnover_component(summary.get("turnover"))

    score = (
        A.BIZ_WEIGHT_TURNOVER * turnover_component
        + A.BIZ_WEIGHT_HEALTHY_CASH * healthy_share
        + A.BIZ_WEIGHT_SELLTHROUGH * sell_through
        + A.BIZ_WEIGHT_AVAILABILITY * max(availability, 0.0)
        + A.BIZ_WEIGHT_DATA_QUALITY * max(data_quality, 0.0)
    ) * 100.0
    score = round(min(max(score, 0.0), 100.0), 1)

    if score >= 80:
        band, verdict = "strong", "The business is running efficiently."
    elif score >= 60:
        band, verdict = "stable", "Solid, with clear room to free up cash."
    elif score >= 40:
        band, verdict = "needs attention", "Too much cash is tied up in slow stock."
    else:
        band, verdict = "at risk", "Most of your cash is frozen on the shelves."

    return {
        "score": score,
        "band": band,
        "verdict": verdict,
        # Every component carries its FORMULA and whether it is measured or
        # assumed. A score whose parts can't be checked is a horoscope, and the
        # owner is entitled to see the arithmetic behind a number that judges
        # his shop. `benchmark` marks a target taken from industry norms rather
        # than from his own history — a target is not a measurement.
        "components": [
            {"key": "turnover", "label": "Inventory turnover",
             "value": summary.get("turnover"),
             "target": f"{A.TURNOVER_BENCHMARK_LOW:.0f}–{A.TURNOVER_BENCHMARK_HIGH:.0f}x",
             "score": round(turnover_component * 100, 1),
             "weight": A.BIZ_WEIGHT_TURNOVER,
             "formula": "period revenue x (365 / period days) / retail inventory value",
             "measured": True, "benchmark": True,
             "caveat": "Revenue and inventory are both at RETAIL, so the ratio is "
                       "comparable year to year but is not a cost-based turnover."},
            {"key": "healthy_cash", "label": "Cash in healthy stock",
             "value": round(healthy_share * 100, 1), "target": "60%+",
             "score": round(healthy_share * 100, 1),
             "weight": A.BIZ_WEIGHT_HEALTHY_CASH,
             "formula": "retail value of healthy/reorder/critical stock / total retail value",
             "measured": True, "benchmark": True},
            {"key": "sell_through", "label": "Sell-through rate",
             "value": round(sell_through * 100, 1), "target": "higher is better",
             "score": round(sell_through * 100, 1),
             "weight": A.BIZ_WEIGHT_SELLTHROUGH,
             "formula": "units sold / (units sold + units on hand)",
             "measured": True, "benchmark": False},
            {"key": "availability", "label": "In-stock rate",
             "value": round(availability * 100, 1), "target": "95%+",
             "score": round(max(availability, 0.0) * 100, 1),
             "weight": A.BIZ_WEIGHT_AVAILABILITY,
             "formula": "1 - (products sold out / products)",
             "measured": True, "benchmark": True,
             "caveat": "A snapshot as of the report date, not an average over the month."},
            {"key": "data_quality", "label": "Data quality",
             "value": round(data_quality * 100, 1), "target": "100%",
             "score": round(max(data_quality, 0.0) * 100, 1),
             "weight": A.BIZ_WEIGHT_DATA_QUALITY,
             "formula": "1 - ((negative stock counts + uncategorised) / products)",
             "measured": True, "benchmark": False,
             "detail": f"{negative} negative stock counts, {uncategorised} uncategorised"},
        ],
        "basis": (
            "Every component is measured from your own report. The WEIGHTS and the "
            "TARGETS are industry benchmarks, not your history — the score is a "
            "consistent yardstick, not a verdict."
        ),
    }


def build(summary, metrics, opportunities) -> dict:
    """The whole Action Center payload, ready for the API."""
    actions = build_actions(opportunities)
    health = business_health(summary, metrics)

    frozen = summary.get("cash_frozen") or 0.0
    inventory = summary.get("inventory_value") or 0.0

    return {
        "business_health": health,
        "headline": {
            "inventory_value": inventory,
            "cash_frozen": frozen,
            "frozen_pct": summary.get("frozen_pct", 0.0),
            "turnover": summary.get("turnover"),
            "opportunity_value": round(sum(o["value_score"] for o in opportunities), 2),
            "opportunity_value_adjusted": round(
                sum(o["ranked_value"] for o in opportunities), 2),
            # Safe to add only because each product now belongs to exactly one
            # opportunity. Summing the raw detector output double-counted every
            # product that appeared in two of them.
            "opportunity_basis": (
                "Each product counts towards one action only — its highest-value "
                "one. Estimated figures depend on assumed rates, which are listed "
                "under “How these numbers were calculated”."
            ),
        },
        "actions": actions,
        "priority_counts": {
            p: sum(1 for a in actions if a["priority"] == p) for p in ("P1", "P2", "P3")
        },
        "assumptions": A.as_disclosure(),
    }
