"""
services/bi/valuation.py — PHASE 22b: retail value vs actual cash

THE PROBLEM THIS SOLVES

Every inventory figure in LiquorIQ is computed from `unit_price`, which is
derived from sales as total ÷ quantity — the SHELF price. The dashboard then
labelled the result "cash frozen":

    Cash frozen   $220,661   70.4% of inventory

The owner never spent $220,661. He spent what his distributor charged him. At a
30% margin the cash actually tied up is about $154,000. Presenting a retail
figure as cash overstates his exposure by his entire margin, and it is the kind
of error he would spot immediately — which costs trust in every other number on
the page.

THE RULE

Margin is never assumed. If the owner hasn't told us his, we show retail and
say "retail value". We do not reach for an industry average and print it as
though it were his. A figure he didn't give us is not his figure.

Pure functions — no DB, no AI.
"""

from app.services.bi import assumptions as A


def normalise_margin(value) -> int | None:
    """
    Accept a sane margin percentage, reject anything else.

    Returns None for unset/garbage, which the callers read as "show retail
    only". A margin of 0 is also None: nobody sells at cost, so a zero is a
    data-entry slip, and treating it literally would claim cost == retail.
    """
    try:
        margin = int(round(float(value)))
    except (TypeError, ValueError):
        return None
    if not (A.GROSS_MARGIN_MIN <= margin <= A.GROSS_MARGIN_MAX):
        return None
    return margin


def at_cost(retail_amount: float, margin_pct: int | None) -> float | None:
    """
    What a retail figure cost the store. None when we have no margin — the
    caller must then show the retail figure and label it as retail.
    """
    margin = normalise_margin(margin_pct)
    if margin is None:
        return None
    return round(float(retail_amount or 0.0) * (1 - margin / 100.0), 2)


def build(summary: dict, margin_pct: int | None) -> dict:
    """
    The valuation block the dashboard renders.

    `basis` tells the UI which word to print. Every consumer reads that flag
    rather than guessing from whether a cost field happens to be present —
    which is how "cash frozen" got printed over a retail number in the first
    place.
    """
    margin = normalise_margin(margin_pct)
    inventory_retail = float(summary.get("inventory_value") or 0.0)
    frozen_retail = float(summary.get("cash_frozen") or 0.0)

    block = {
        "basis": "cost" if margin else "retail",
        "gross_margin_pct": margin,
        "inventory_retail": round(inventory_retail, 2),
        "frozen_retail": round(frozen_retail, 2),
        "inventory_cost": at_cost(inventory_retail, margin),
        "frozen_cost": at_cost(frozen_retail, margin),
        # The word the UI puts on the big number, so the label and the figure
        # can never drift apart.
        "inventory_label": "Inventory at cost" if margin else "Inventory value (retail)",
        "frozen_label": "Cash frozen" if margin else "Slow stock (retail value)",
        "note": (
            f"Cost estimated from your {margin}% gross margin."
            if margin else
            "Your POS export has no cost data. These are RETAIL values — what "
            "the stock would sell for, not what it cost you. Add your gross "
            "margin to see the cash actually tied up."
        ),
    }
    block["inventory_headline"] = (block["inventory_cost"] if margin
                                   else block["inventory_retail"])
    block["frozen_headline"] = block["frozen_cost"] if margin else block["frozen_retail"]
    return block
