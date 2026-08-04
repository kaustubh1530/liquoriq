"""
services/bi/seasonality.py — WHICH products actually sell for a holiday

THE PROBLEM THIS SOLVES

The seasonal detector used to scope every product the store held:

    Labor Day Weekend is 28 days away
    Stock in scope: $310,591        ← 99% of the entire inventory
    Around $46,589 of additional sales

That is not a Labor Day opportunity. It is 15% of everything with a holiday
name on it. Nobody buys Cognac for a barbecue, and telling an owner otherwise
teaches him to ignore the panel.

TWO CHANGES

1. RELEVANCE. Each holiday names the categories that genuinely move for it,
   plus keywords for cases the category alone can't express — St Patrick's is
   IRISH whiskey, not all whiskey. Every qualifying product carries a reason,
   so the owner can check the judgement instead of trusting it.

2. THE VALUE IS BASED ON SALES, NOT STOCK. The old figure was 15% of the
   RETAIL VALUE OF SHELF STOCK, which rewards holding more inventory — a
   store with a dead warehouse would show a bigger "opportunity" than one that
   sells briskly. The uplift now applies to what those categories ACTUALLY
   SOLD in the period, which is measured, and is then capped by the stock on
   hand because you cannot sell what you do not have.

Pure functions — no DB, no AI.
"""

import re

# Per-holiday relevance. `categories` are the resolved Category Intelligence
# names; `keywords` qualify a product whose category is too broad on its own.
# `lift` is the share of normal category sales the holiday is expected to add —
# an ASSUMPTION, and reported as one everywhere it is used.
HOLIDAY_RULES: dict[str, dict] = {
    "new_years_eve": {
        "categories": ["Champagne", "Wine", "Whiskey", "Vodka"],
        "keywords": ["prosecco", "cava", "sparkling", "brut"],
        "lift": 0.35, "note": "Champagne and premium spirits peak on New Year's Eve",
    },
    "valentines": {
        "categories": ["Champagne", "Wine", "Liqueur"],
        "keywords": ["rose", "rosé", "prosecco", "cream"],
        "lift": 0.15, "note": "Wine, Champagne and gift bottles for couples",
    },
    "super_bowl": {
        "categories": ["Beer", "Seltzer/RTD", "Tequila", "Vodka"],
        "keywords": ["12 pack", "12pk", "24 pack", "case", "lite"],
        "lift": 0.30, "note": "Beer cases and party spirits — the biggest beer day",
    },
    "mardi_gras": {
        "categories": ["Rum", "Whiskey", "Liqueur"],
        "keywords": ["hurricane", "spiced"],
        "lift": 0.10, "note": "Festive cocktails, rum-led",
    },
    "st_patricks": {
        "categories": ["Whiskey", "Beer", "Liqueur"],
        "keywords": ["irish", "jameson", "guinness", "stout", "bailey", "tullamore"],
        "lift": 0.25, "note": "Irish whiskey and stout specifically, not all whiskey",
    },
    "kentucky_derby": {
        "categories": ["Whiskey"],
        "keywords": ["bourbon", "kentucky", "mint"],
        "lift": 0.15, "note": "Bourbon season",
    },
    "cinco_de_mayo": {
        "categories": ["Tequila", "Beer"],
        "keywords": ["mezcal", "margarita", "corona", "modelo", "dos equis", "pacifico"],
        "lift": 0.35, "note": "Tequila and Mexican beer",
    },
    "memorial_day": {
        "categories": ["Beer", "Seltzer/RTD", "Wine"],
        "keywords": ["rose", "rosé", "lite", "12 pack", "12pk", "case"],
        "lift": 0.20, "note": "Start of BBQ season — beer, seltzer, rosé",
    },
    "fathers_day": {
        "categories": ["Whiskey", "Beer"],
        "keywords": ["bourbon", "scotch", "single malt", "craft", "reserve"],
        "lift": 0.12, "note": "Premium whiskey and craft beer as gifts",
    },
    "independence_day": {
        "categories": ["Beer", "Seltzer/RTD", "Vodka", "Wine"],
        "keywords": ["rose", "rosé", "lite", "12 pack", "12pk", "case", "seltzer"],
        "lift": 0.30, "note": "Beer and seltzer weekend",
    },
    "labor_day": {
        "categories": ["Beer", "Seltzer/RTD", "Tequila"],
        "keywords": ["rose", "rosé", "lite", "12 pack", "12pk", "case", "margarita"],
        "lift": 0.20, "note": "Last summer BBQ push — beer, seltzer, tequila",
    },
    "oktoberfest": {
        "categories": ["Beer"],
        "keywords": ["marzen", "märzen", "oktoberfest", "lager", "german", "craft"],
        "lift": 0.15, "note": "German and craft lager season",
    },
    "halloween": {
        "categories": ["Vodka", "Rum", "Wine"],
        "keywords": ["pumpkin", "spiced", "cider"],
        "lift": 0.10, "note": "Party spirits and themed cocktails",
    },
    "diwali": {
        "categories": ["Whiskey", "Wine", "Champagne"],
        "keywords": ["reserve", "single malt", "gift"],
        "lift": 0.15, "note": "Premium gifting",
    },
    "blackout_wednesday": {
        "categories": ["Beer", "Whiskey", "Vodka", "Seltzer/RTD"],
        "keywords": ["12 pack", "12pk", "case", "lite"],
        "lift": 0.30, "note": "One of the busiest liquor nights of the year",
    },
    "thanksgiving": {
        "categories": ["Wine", "Champagne", "Whiskey"],
        "keywords": ["pinot", "chardonnay", "beaujolais", "cider", "cabernet", "red blend"],
        "lift": 0.25, "note": "Wine for the table plus hosting spirits",
    },
    "christmas": {
        "categories": ["Champagne", "Whiskey", "Wine", "Liqueur"],
        "keywords": ["gift", "reserve", "single malt", "eggnog", "cream", "sparkling"],
        "lift": 0.30, "note": "Peak gifting season",
    },
}

# Applied when a holiday has no rule yet. Deliberately narrow and cautious:
# an unknown holiday should under-claim, not scope the whole shop.
FALLBACK_RULE = {"categories": [], "keywords": [], "lift": 0.10,
                 "note": "no specific rule for this holiday"}


def rule_for(holiday_key: str) -> dict:
    return HOLIDAY_RULES.get(holiday_key or "", FALLBACK_RULE)


# Categories that never belong in a drinks promotion, however their names read.
# The validation report caught "CAMEL LIGHTS BOX" qualifying for a Labor Day
# barbecue because the keyword "light" matched. Cigarettes are not a holiday
# drink, and one absurd item on a campaign list discredits the other 500.
NEVER_SEASONAL = {"Tobacco", "Snacks", "Non-product", "Non-alcoholic"}


def _matched_keyword(name: str, keywords: list[str]) -> str | None:
    lowered = (name or "").lower()
    for word in keywords:
        if re.search(rf"\b{re.escape(word)}", lowered):
            return word
    return None


def qualify(metrics: list[dict], holiday_key: str, holiday_name: str) -> list[dict]:
    """
    The products that genuinely belong in this holiday's campaign, each with a
    plain-English reason it qualified.

    A product must also HAVE STOCK — promoting something that's sold out
    generates demand the shop can't serve, which is worse than not promoting.
    """
    rule = rule_for(holiday_key)
    categories = set(rule["categories"])
    keywords = rule["keywords"]

    qualified = []
    for m in metrics:
        if (m.get("stock") or 0) <= 0:
            continue

        category = m.get("category")
        if category in NEVER_SEASONAL:
            continue

        keyword = _matched_keyword(m.get("product_name", ""), keywords)

        if category in categories:
            reason = f"{category} is a core {holiday_name} category"
            if keyword:
                reason += f", and the name matches “{keyword}”"
            basis = "category"
        elif keyword:
            reason = f"name matches “{keyword}”, which sells for {holiday_name}"
            basis = "keyword"
        else:
            continue

        qualified.append({**m, "qualified_because": reason, "qualified_by": basis})

    return qualified


def expected_uplift(qualified: list[dict], holiday_key: str) -> dict:
    """
    Expected incremental sales, grounded in what these products ACTUALLY SOLD.

    value = (their sales this period) x (the holiday's assumed lift)

    Capped at the retail value of stock on hand: you cannot sell what you do
    not have, and an uncapped figure would promise sales the shelf can't cover.

    Returns the parts as well as the total, so the card can show its working.
    """
    rule = rule_for(holiday_key)
    base_revenue = sum(m["revenue"] for m in qualified)
    stock_value = sum(m["inventory_value"] for m in qualified)

    raw = base_revenue * rule["lift"]
    capped = min(raw, stock_value)

    return {
        "value": round(capped, 2),
        "base_revenue": round(base_revenue, 2),
        "lift_rate": rule["lift"],
        "uncapped": round(raw, 2),
        "stock_value": round(stock_value, 2),
        "capped_by_stock": capped < raw,
        "categories": sorted(set(rule["categories"])),
        "note": rule["note"],
        "products": len(qualified),
    }
