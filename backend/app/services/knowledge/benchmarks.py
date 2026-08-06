"""
services/knowledge/benchmarks.py — PHASE 24: what "good" looks like.

A number with no benchmark is trivia. 2.46x turnover means nothing to a shop
owner until someone says a healthy independent runs 4–6x — at which point it
means "your cash is moving half as fast as it should".

WHERE THESE COME FROM, AND WHERE THEY DON'T

These are INDUSTRY figures for US independent liquor retail, not measurements
of any particular store. Every one is labelled as such wherever it surfaces,
because the Phase 22 lesson stands: an assumption presented as a fact is the
fastest way to lose the owner's trust in everything else on the page.

The engine's own thresholds live in services/bi/assumptions.py and drive
calculations. These are the INTERPRETIVE layer — they explain rather than
compute, and nothing here feeds a number back into the BI engine.
"""

BENCHMARKS = {
    "inventory_turnover": {
        "label": "Inventory turnover",
        "healthy": "4–6x per year",
        "bands": [
            (6.0, "excellent", "Stock is working hard. Watch for stock-outs."),
            (4.0, "healthy", "Cash is cycling at a normal rate."),
            # 2.0 is half the healthy floor. Below that the shop is not slow,
            # it is illiquid — a distinction worth keeping, so that "high risk"
            # still means something when it appears.
            (2.0, "needs attention", "Roughly half the industry norm — too much "
                                     "cash is sitting still."),
            (0.0, "high risk", "Stock is barely moving. This is a buying "
                               "problem, not a selling problem."),
        ],
        "note": "Independents typically run lower than chains because they "
                "carry deeper assortments on the same shelf space.",
    },
    "sell_through": {
        "label": "Sell-through rate",
        "healthy": "40–60% per period",
        "bands": [
            (0.60, "excellent", "Very little dead weight in the range."),
            (0.40, "healthy", "Normal for a full-assortment independent."),
            (0.25, "needs attention", "A large share of the range is not moving."),
            (0.0, "high risk", "Most of what you carry did not sell this period."),
        ],
        "note": "Measured as units sold ÷ (units sold + units on hand).",
    },
    "weeks_of_supply": {
        "label": "Stock coverage",
        "healthy": "6–8 weeks",
        "bands": [
            (52.0, "sleeping", "Over a year of stock. This will not clear itself."),
            (26.0, "dead weight", "Six months or more. Clearance candidate."),
            (12.0, "heavy", "Three months. Stop reordering."),
            (3.0, "healthy", "Comfortable cover."),
            (0.0, "at risk", "Under three weeks. Reorder now."),
        ],
        "note": "Spirits tolerate deeper cover than beer, which is perishable.",
    },
    "business_health": {
        "label": "Business health score",
        "healthy": "75+",
        "bands": [
            (90.0, "excellent", "Running efficiently on every measure."),
            (75.0, "healthy", "Solid, with room to free up cash."),
            (60.0, "needs attention", "One or two measures are dragging."),
            (40.0, "at risk", "Too much cash is tied up in stock that isn't moving."),
            (0.0, "critical", "The business is illiquid in inventory terms."),
        ],
        "note": "A composite of turnover, healthy-stock share, sell-through, "
                "availability and data quality. The weights are ours; the "
                "component figures are measured from the store's own report.",
    },
    "gross_margin": {
        "label": "Gross margin",
        "healthy": "22–30% spirits, 30–40% wine, 25–30% beer",
        "bands": [],
        "note": "Varies by state and by how much of the range is on deal. Only "
                "shown when the owner supplies his own figure.",
    },
}


def interpret(metric: str, value: float | None) -> dict | None:
    """
    Turn a raw figure into a verdict the owner can act on.

    Returns the band, the benchmark it was judged against, and an explicit
    statement that the benchmark is an industry figure rather than his history.
    """
    spec = BENCHMARKS.get(metric)
    if not spec or value is None:
        return None

    band, meaning = "unknown", ""
    for threshold, name, description in spec["bands"]:
        if value >= threshold:
            band, meaning = name, description
            break

    return {
        "metric": spec["label"],
        "value": value,
        "band": band,
        "meaning": meaning,
        "healthy_range": spec["healthy"],
        "note": spec["note"],
        "basis": "industry benchmark, not this store's history",
    }


def as_prompt_block(base_context: dict) -> str:
    """The store's headline figures, each with its verdict, for the model."""
    numbers = base_context.get("headline_numbers") or {}
    health = base_context.get("business_health") or {}

    readings = [
        interpret("inventory_turnover", numbers.get("inventory_turnover")),
        interpret("sell_through", numbers.get("sell_through_rate")),
        interpret("business_health", health.get("score")),
    ]
    readings = [r for r in readings if r]
    if not readings:
        return ""

    lines = ["INDUSTRY BENCHMARKS — how this store reads against the trade. "
             "These ranges are industry figures, NOT measurements of this shop; "
             "say so when you use them:"]
    for r in readings:
        lines.append(
            f"\n· {r['metric']}: {r['value']} — {r['band']}. "
            f"Healthy is {r['healthy_range']}. {r['meaning']}"
        )
    return "\n".join(lines)
