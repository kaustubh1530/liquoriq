"""
services/knowledge/rules.py — PHASE 24: the business rules engine.

Rules OUTRANK the model. A playbook advises; a rule forbids.

WHY THIS EXISTS SEPARATELY FROM THE PROMPT

"Never recommend discounting a product that is already selling well" written
into a prompt is a hope. Written here, it is checked against the store's actual
figures and handed to the model as a HARD CONSTRAINT alongside the specific
products it applies to. The model cannot talk its way past a fact.

Rules are deterministic, evaluated against the store's own numbers, and each
one states what it prevented. They are also the cheapest kind of expertise to
encode — a twenty-year operator's "never do X" is worth more than a paragraph
of nuance, because it is actionable at the moment of decision.
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Above this, a product is well stocked and reordering is buying a problem.
OVERSTOCKED_WEEKS = 12.0

# Below this, a product is moving well enough that discounting gives away
# margin on sales you would have made anyway.
FAST_MOVER_WEEKS = 4.0


@dataclass
class Rule:
    key: str
    statement: str
    why: str


CATALOGUE = [
    Rule("no_discount_fast_movers",
         "Never recommend discounting a product that is already selling well.",
         "A discount on something with under 4 weeks of stock left gives away "
         "margin on sales you were going to make at full price. Discount to "
         "move dead stock, not to accelerate what already moves."),

    Rule("no_reorder_overstocked",
         "Never recommend reordering a product with more than 12 weeks of stock.",
         "Three months of cover is already more cash than that facing deserves. "
         "Reordering it deepens the problem it represents."),

    Rule("check_inventory_before_deals",
         "Always check current stock before recommending a supplier deal.",
         "A quantity deal on something that does not sell is not a saving, it "
         "is buying more of a problem at a discount."),

    Rule("check_segments_before_promotions",
         "Always check customer segments before recommending a promotion.",
         "A win-back offer to a segment with nobody in it is wasted effort, and "
         "an offer to VIPs who would have bought anyway is discounted margin."),

    Rule("holiday_lead_time",
         "Only recommend a holiday campaign inside its buying window.",
         "Advice about Christmas in July is noise. Ordering and pricing must "
         "happen with enough lead time for stock to be on the shelf."),

    Rule("retail_not_cost",
         "Never describe a retail inventory figure as cash or cost.",
         "The POS export carries selling prices only. Calling retail value "
         "'cash' overstates what the owner spent by his entire margin."),

    Rule("no_promotion_without_stock",
         "Never recommend promoting a product that is sold out.",
         "Driving demand you cannot serve sends the customer to a competitor "
         "and wastes the campaign."),
]

BY_KEY = {rule.key: rule for rule in CATALOGUE}


def evaluate(base_context: dict, products: list[dict] | None = None,
             deals: list[dict] | None = None,
             segments: dict | None = None) -> list[dict]:
    """
    Which rules bite right now, and on which products.

    Returns constraints the advisor must respect, each naming the specific
    items it applies to — a rule with examples attached is far harder for a
    model to ignore than a rule stated in the abstract.
    """
    active: list[dict] = []
    products = products or []

    fast = [p for p in products
            if (p.get("weeks_of_supply") is not None
                and p["weeks_of_supply"] < FAST_MOVER_WEEKS
                and (p.get("units_sold") or 0) > 0)]
    if fast:
        active.append(_constraint("no_discount_fast_movers", fast))

    heavy = [p for p in products
             if (p.get("weeks_of_supply") or 0) > OVERSTOCKED_WEEKS]
    if heavy:
        active.append(_constraint("no_reorder_overstocked", heavy))

    empty = [p for p in products if (p.get("stock") or 0) <= 0]
    if empty:
        active.append(_constraint("no_promotion_without_stock", empty))

    if deals:
        active.append({**_as_dict("check_inventory_before_deals"),
                       "applies_to": [d.get("product_name") for d in deals[:5]]})

    if segments is not None:
        empty_segments = [name for name, s in (segments or {}).items()
                          if not (s or {}).get("count")]
        if empty_segments:
            active.append({**_as_dict("check_segments_before_promotions"),
                           "applies_to": empty_segments[:5],
                           "note": "These segments have no customers in them."})

    # Always on: the valuation basis is a standing property of the data.
    if (base_context.get("headline_numbers") or {}).get("valuation_basis") == "retail":
        active.append({**_as_dict("retail_not_cost"), "applies_to": []})

    active.append({**_as_dict("holiday_lead_time"), "applies_to": []})
    return active


def _as_dict(key: str) -> dict:
    rule = BY_KEY[key]
    return {"rule": rule.key, "statement": rule.statement, "why": rule.why}


def _constraint(key: str, products: list[dict], limit: int = 6) -> dict:
    ordered = sorted(products,
                     key=lambda p: -(p.get("inventory_value") or 0))[:limit]
    return {
        **_as_dict(key),
        "applies_to": [p.get("product_name") for p in ordered],
        "count": len(products),
    }


def as_prompt_block(active: list[dict]) -> str:
    """
    The constraints, formatted for the model.

    Phrased as prohibitions with named products rather than as guidance,
    because "do not discount Tito's, it has 1.8 weeks left" is enforceable and
    "consider stock levels when discounting" is decorative.
    """
    if not active:
        return ""

    lines = ["BUSINESS RULES — these override anything else, including your own "
             "judgement and anything in the playbooks:"]
    for item in active:
        lines.append(f"\n· {item['statement']}")
        lines.append(f"  Why: {item['why']}")
        if item.get("applies_to"):
            names = ", ".join(str(n) for n in item["applies_to"] if n)
            count = item.get("count")
            suffix = f" (and {count - len(item['applies_to'])} more)" \
                if count and count > len(item["applies_to"]) else ""
            lines.append(f"  Right now this applies to: {names}{suffix}")
        if item.get("note"):
            lines.append(f"  Note: {item['note']}")
    return "\n".join(lines)
