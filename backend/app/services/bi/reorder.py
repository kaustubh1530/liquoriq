"""
services/bi/reorder.py — PHASE 22: the reorder list as a PURCHASE DOCUMENT

The Action Center can tell the owner "1,128 products need reordering". That is
a finding, not something he can act on. What he actually needs is a list he can
hand to his distributor rep: what to buy, how many, and what it will cost.

This module turns metrics into that list. Pure functions — no DB, no AI.

TWO HONESTY RULES, both load-bearing:

1. THE SUGGESTED QUANTITY COVERS THE HORIZON, NOT THE SHELF. It is
   (weekly sales rate x horizon) MINUS what is already on hand — so a product
   with two weeks of stock left on a four-week horizon is ordered for two
   weeks, not four. Ignoring stock on hand is how a reorder tool talks a shop
   into double-buying.

2. THE MONEY COLUMN IS RETAIL VALUE, NOT COST. The POS export contains no
   cost price, so we cannot state what an order will cost. Calling a retail
   figure "cost" would overstate the owner's outlay by his entire margin. It
   is named and labelled as retail value everywhere, including the CSV.
"""

import math

from app.services.bi import assumptions as A

# Only these classes are genuinely short. "healthy" is not a reorder candidate
# however well it sells, and "dead" stock does not need buying more of.
REORDER_CLASSES = ("sold_out", "critical", "reorder")

URGENCY = {
    "sold_out": ("Out of stock", 1),
    "critical": ("Under 1 week", 2),
    "reorder":  ("Under 3 weeks", 3),
}


def suggested_quantity(weekly_velocity: float, stock: float,
                       horizon_weeks: float) -> int:
    """
    Units to order to cover `horizon_weeks` of demand, net of stock on hand.

    Rounded UP: ordering 4 when the shortfall is 3.2 is the harmless direction
    to be wrong in, and distributors sell whole bottles.
    """
    shortfall = (weekly_velocity * horizon_weeks) - max(stock, 0.0)
    return int(math.ceil(shortfall)) if shortfall > 0 else 0


def build_reorder_list(metrics: list[dict], horizon_weeks: float | None = None) -> list[dict]:
    """One row per product worth reordering, most valuable first."""
    horizon = horizon_weeks or A.REORDER_HORIZON_WEEKS
    rows = []

    for m in metrics:
        if m["stock_class"] not in REORDER_CLASSES or m["units_sold"] <= 0:
            continue
        quantity = suggested_quantity(m["weekly_velocity"], m["stock"], horizon)
        if quantity <= 0:
            continue

        label, rank = URGENCY[m["stock_class"]]
        rows.append({
            "product_name": m["product_name"],
            "sku": m["sku"] or "",
            "category": m.get("category") or "Other",
            "urgency": label,
            "urgency_rank": rank,
            "stock_on_hand": m["stock"],
            "units_sold_in_period": m["units_sold"],
            "weekly_sales_rate": m["weekly_velocity"],
            "weeks_of_supply": m["weeks_of_supply"],
            "suggested_quantity": quantity,
            "unit_price": m["unit_price"],
            # RETAIL value, not cost — see the module docstring.
            "line_value_at_retail": round(quantity * m["unit_price"], 2),
        })

    # Most urgent first, then by value: the rep's time is limited and the top of
    # the list should be the part that matters if he only gets through half.
    rows.sort(key=lambda r: (r["urgency_rank"], -r["line_value_at_retail"]))
    return rows


def summarise(rows: list[dict], horizon_weeks: float | None = None) -> dict:
    """Totals for the panel header."""
    horizon = horizon_weeks or A.REORDER_HORIZON_WEEKS
    return {
        "products": len(rows),
        "total_units": sum(r["suggested_quantity"] for r in rows),
        "total_value_at_retail": round(sum(r["line_value_at_retail"] for r in rows), 2),
        "out_of_stock": sum(1 for r in rows if r["urgency_rank"] == 1),
        "horizon_weeks": horizon,
    }


CSV_COLUMNS = [
    ("product_name", "Product"),
    ("sku", "SKU"),
    ("category", "Category"),
    ("urgency", "Urgency"),
    ("stock_on_hand", "Stock on hand"),
    ("units_sold_in_period", "Units sold in period"),
    ("weekly_sales_rate", "Weekly sales rate"),
    ("suggested_quantity", "Suggested order qty"),
    ("unit_price", "Retail price"),
    ("line_value_at_retail", "Line value at retail"),
]
