"""
services/bi/planning.py — WHEN to do it, and over how long

THE PROBLEM THIS SOLVES

The clearance card said:

    P1 · Do this now
    $220,661 is frozen in 466 slow-moving products
    Free up roughly $132,396 in cash

$132,396 is TWO MONTHS OF THE STORE'S ENTIRE REVENUE ($66,753/month). No
independent shop clears that in a week, and labelling it "do this now" makes
the whole dashboard feel written by someone who has never stood behind a
counter. A recommendation without a timeframe isn't a plan, it's a wish.

So: every opportunity gets a realistic execution window, and anything larger
than the store can absorb in one go becomes a PHASED plan sized against its
own revenue.

The capacity assumption is stated, not hidden — see CLEARANCE_CAPACITY_PCT.

Pure functions — no DB, no AI.
"""

import math

from app.services.bi import assumptions as A

# Windows, shortest first. Used for display and for sorting a day's work.
TIMELINES = ["Today", "This week", "Next 2 weeks", "This month", "This quarter"]


def _by_days(days: float | None) -> str:
    """Map a lead time in days onto a window the owner actually thinks in."""
    if days is None:
        return "This month"
    if days <= 1:
        return "Today"
    if days <= 7:
        return "This week"
    if days <= 14:
        return "Next 2 weeks"
    if days <= 31:
        return "This month"
    return "This quarter"


def timeline_for(kind: str, evidence: dict | None = None) -> dict:
    """
    The execution window for one opportunity, with the reason for it.

    Deadline-driven work (a holiday) is dated by the event. Everything else is
    paced by how quickly acting actually pays: a stock-out costs sales every
    day it persists, whereas an upsell tag can wait for a quiet afternoon.
    """
    evidence = evidence or {}

    if kind == "reorder":
        # Every day out of stock is sales lost that cannot be recovered later.
        out_of_stock = evidence.get("products_out_of_stock") or 0
        if out_of_stock:
            return {"timeline": "Today",
                    "timeline_reason": f"{out_of_stock} products are on the floor "
                                       "sold out — each day is sales you can't get back"}
        return {"timeline": "This week",
                "timeline_reason": "these run out within three weeks at the current rate"}

    if kind == "seasonal":
        days = evidence.get("days_away")
        holiday = evidence.get("holiday", "the holiday")
        # Stock and promotion have to be in place BEFORE the weekend, not on it.
        lead = max(0, (days or 0) - 7)
        return {"timeline": f"Before {holiday}",
                "timeline_days": days,
                "timeline_reason": f"{days} days away — order and price it in the "
                                   f"next {lead} days so it's on the shelf in time"}

    if kind == "clearance":
        return {"timeline": "This quarter",
                "timeline_reason": "too large to clear at once — run it in phases"}

    if kind == "campaign_repeat":
        return {"timeline": "This week",
                "timeline_reason": "it already worked once; there is nothing to design"}

    if kind == "winback":
        return {"timeline": "Next 2 weeks",
                "timeline_reason": "no deadline, but lapsed customers drift further "
                                   "the longer you leave them"}

    if kind in ("bundle", "premium_upsell"):
        return {"timeline": "This month",
                "timeline_reason": "shelf work — do it on a quiet afternoon"}

    return {"timeline": _by_days(None), "timeline_reason": ""}


def clearance_phases(stuck: list[dict], period_revenue: float,
                     period_days: int) -> dict:
    """
    Break a clearance too big to run at once into phases the shop can absorb.

    THE CAPACITY MODEL. A clearance competes with normal trade for the same
    customers and the same shelf space. CLEARANCE_CAPACITY_PCT caps how much
    extra revenue one month of clearance can realistically produce, as a share
    of normal monthly revenue. It is an ASSUMPTION and is reported as one.

    Phases run worst-first: stock sitting on more than a year of supply is
    costing the most and is least likely to sell on its own.
    """
    if not stuck:
        return {"phases": [], "months_to_clear": 0, "monthly_capacity": 0.0}

    monthly_revenue = (period_revenue / max(period_days, 1)) * 30.0
    monthly_capacity = monthly_revenue * A.CLEARANCE_CAPACITY_PCT
    recoverable = sum(m["cash_frozen"] for m in stuck) * A.CLEARANCE_RECOVERY_RATE
    months = math.ceil(recoverable / monthly_capacity) if monthly_capacity > 0 else 0

    # Worst first: longest-sitting, then largest position.
    rank = {"dead": 0, "sleeping": 1, "overstock": 2}
    ordered = sorted(stuck, key=lambda m: (rank.get(m["stock_class"], 3), -m["cash_frozen"]))

    definitions = [
        ("Phase 1", "This month", "Deepest discounts on the worst offenders — "
                                  "stock that has sat for over a year"),
        ("Phase 2", "Next month", "Moderate discounts on the remaining slow movers"),
        ("Phase 3", "This quarter", "Bundle or tag the rest alongside your best sellers"),
    ]

    phases, cursor = [], 0
    for index, (name, window, description) in enumerate(definitions):
        if cursor >= len(ordered):
            break
        budget, taken, value = monthly_capacity, [], 0.0
        while cursor < len(ordered):
            item = ordered[cursor]
            gain = item["cash_frozen"] * A.CLEARANCE_RECOVERY_RATE
            # Always take at least one, or a single big position stalls the plan.
            if taken and value + gain > budget:
                break
            taken.append(item)
            value += gain
            cursor += 1
        # The last phase sweeps up whatever is left rather than leaving a tail.
        if index == len(definitions) - 1:
            while cursor < len(ordered):
                item = ordered[cursor]
                taken.append(item)
                value += item["cash_frozen"] * A.CLEARANCE_RECOVERY_RATE
                cursor += 1

        phases.append({
            "phase": name,
            "timeline": window,
            "description": description,
            "products": len(taken),
            "cash_frozen": round(sum(m["cash_frozen"] for m in taken), 2),
            "estimated_recovery": round(value, 2),
            "top_items": [m["product_name"] for m in taken[:5]],
        })

    return {
        "phases": phases,
        "months_to_clear": months,
        "monthly_capacity": round(monthly_capacity, 2),
        "monthly_revenue": round(monthly_revenue, 2),
        "capacity_pct": A.CLEARANCE_CAPACITY_PCT,
        "basis": (
            f"Assumes a clearance can add about {A.CLEARANCE_CAPACITY_PCT:.0%} to a "
            f"normal month's sales (${monthly_revenue:,.0f}), so roughly "
            f"${monthly_capacity:,.0f} of recovery per month. This is an assumption, "
            f"not a measurement."
        ),
    }
