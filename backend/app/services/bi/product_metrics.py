"""
services/bi/product_metrics.py — PHASE 22: per-product intelligence

One product row in → one enriched record out: velocity, weeks of supply,
sell-through, turnover, cash frozen, a stock CLASS, a HEALTH score and an
OPPORTUNITY score.

Two decisions worth knowing about:

1. VELOCITY USES THE FILE'S REAL PERIOD, not a hard-coded 4.3 weeks. The old
   code assumed every upload covered a month; a WEEKLY upload therefore
   understated velocity 4x and made every reorder and overstock verdict wrong.

2. HEALTH AND OPPORTUNITY ARE DIFFERENT QUESTIONS, so they are different
   scores. Health asks "is this product doing well?". Opportunity asks "how
   much is there to gain by acting on it?". A sold-out best-seller is healthy
   AND a big opportunity. A dead $2 item is unhealthy and worth ignoring.
   Ranking a to-do list by health would put the trivia at the top.

Pure functions — no DB, no network, no AI.
"""

from app.services.bi import assumptions as A

# Stock classes, worst-to-best for display ordering.
CLASSES = [
    "negative", "sold_out", "dead", "critical", "reorder",
    "healthy", "heavy", "overstock", "sleeping",
]

CLASS_LABELS = {
    "negative":  "Negative stock — count is wrong",
    "sold_out":  "Sold out — losing sales",
    "dead":      "Dead — never moved",
    "critical":  "Critical — under 1 week left",
    "reorder":   "Reorder — under 3 weeks left",
    "healthy":   "Healthy",
    "heavy":     "Heavy — 3 to 6 months",
    "overstock": "Overstock — 6 to 12 months",
    "sleeping":  "Sleeping — over a year of stock",
}

# How urgent acting on this class is (0-1), used by the opportunity score.
CLASS_URGENCY = {
    "sold_out": 1.00, "critical": 0.95, "reorder": 0.75, "negative": 0.60,
    "sleeping": 0.70, "dead": 0.65, "overstock": 0.45, "heavy": 0.20,
    "healthy": 0.05,
}

# Classes where cash is stuck rather than working.
FROZEN_CLASSES = {"dead", "sleeping", "overstock"}


def _num(value) -> float:
    """Tolerant float: None/""/NaN all become 0.0 rather than exploding."""
    try:
        out = float(value)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if out != out else out


def classify(units_sold: float, stock: float, weeks_of_supply: float | None) -> str:
    """
    The 9 stock classes. Order matters — the first match wins, and the
    data-quality and availability cases are checked before anything derived
    from them, because a negative stock count makes every ratio meaningless.
    """
    if stock < 0:
        return "negative"
    if stock == 0:
        return "sold_out" if units_sold > 0 else "dead"
    if units_sold <= 0:
        return "dead"
    if weeks_of_supply is None:
        return "healthy"
    if weeks_of_supply < A.CRITICAL_WEEKS:
        return "critical"
    if weeks_of_supply < A.REORDER_WEEKS:
        return "reorder"
    if weeks_of_supply <= A.HEALTHY_MAX_WEEKS:
        return "healthy"
    if weeks_of_supply <= A.HEAVY_MAX_WEEKS:
        return "heavy"
    if weeks_of_supply <= A.OVERSTOCK_MAX_WEEKS:
        return "overstock"
    return "sleeping"


def _supply_score(weeks: float | None, stock_class: str) -> float:
    """
    0-1 for how well-balanced the stock level is. Peaks inside the healthy band
    and falls off in BOTH directions — too little is as wrong as too much.
    """
    if stock_class in ("sold_out", "negative"):
        return 0.0
    if stock_class == "dead":
        return 0.05
    if weeks is None:
        return 0.5
    if A.REORDER_WEEKS <= weeks <= A.HEALTHY_MAX_WEEKS:
        return 1.0
    if weeks < A.REORDER_WEEKS:                       # running out
        return max(0.0, weeks / A.REORDER_WEEKS) * 0.8
    # Too much: decay from the top of healthy out to the sleeping threshold
    span = A.OVERSTOCK_MAX_WEEKS - A.HEALTHY_MAX_WEEKS
    over = min(weeks - A.HEALTHY_MAX_WEEKS, span)
    return max(0.05, 1.0 - (over / span))


def compute(
    product: dict,
    period_days: int,
    max_cash: float = 0.0,
    revenue_percentile: float = 0.5,
    units_percentile: float = 0.5,
) -> dict:
    """
    Enrich one product.

    product: {product_name, sku, category, quantity, unit_price, total_amount,
              stock_on_hand}
    period_days: the TRUE length of the reporting period.
    max_cash: the store's largest single frozen position, used to scale the
              money component of the opportunity score. Passing 0 disables it.
    *_percentile: this product's rank within the store (0-1), computed by the
              caller once for the whole set.
    """
    period_days = max(1, int(period_days or A.DEFAULT_PERIOD_DAYS))
    weeks_in_period = period_days / 7.0

    units = _num(product.get("quantity"))
    stock = _num(product.get("stock_on_hand"))
    price = _num(product.get("unit_price"))
    revenue = _num(product.get("total_amount"))

    weekly_velocity = units / weeks_in_period if weeks_in_period else 0.0
    weeks_of_supply = (stock / weekly_velocity) if weekly_velocity > 0 and stock > 0 else None

    denominator = units + max(stock, 0)
    sell_through = (units / denominator) if denominator > 0 else 0.0

    # Annualised turnover for this product: how many times its shelf position
    # empties in a year at the current rate.
    periods_per_year = 365.0 / period_days
    turnover = ((units * periods_per_year) / stock) if stock > 0 else None

    cash = max(stock, 0.0) * price
    stock_class = classify(units, stock, weeks_of_supply)

    # ── Health: is this product doing well? ──
    health = (
        A.HEALTH_WEIGHT_SUPPLY * _supply_score(weeks_of_supply, stock_class)
        + A.HEALTH_WEIGHT_SELLTHROUGH * min(sell_through, 1.0)
        + A.HEALTH_WEIGHT_REVENUE * revenue_percentile
        + A.HEALTH_WEIGHT_AVAILABILITY * (0.0 if stock_class in ("sold_out", "negative") else 1.0)
    ) * 100.0

    # ── Opportunity: how much is there to GAIN by acting? ──
    # Money at stake is cash frozen for the overstocked classes, but for a
    # sold-out product it's the revenue we're failing to earn.
    if stock_class in FROZEN_CLASSES:
        money_at_stake = cash
    elif stock_class in ("sold_out", "critical", "reorder"):
        money_at_stake = weekly_velocity * price * A.REORDER_HORIZON_WEEKS
    else:
        money_at_stake = 0.0
    money_component = min(money_at_stake / max_cash, 1.0) if max_cash > 0 else 0.0

    opportunity = (
        A.OPP_WEIGHT_MONEY * money_component
        + A.OPP_WEIGHT_URGENCY * CLASS_URGENCY.get(stock_class, 0.0)
        + A.OPP_WEIGHT_DEMAND * units_percentile
    ) * 100.0

    return {
        "product_name": product.get("product_name"),
        "sku": product.get("sku"),
        "category": product.get("category"),
        "units_sold": round(units, 2),
        "stock": round(stock, 2),
        "unit_price": round(price, 2),
        "revenue": round(revenue, 2),
        "weekly_velocity": round(weekly_velocity, 3),
        "weeks_of_supply": (round(weeks_of_supply, 1) if weeks_of_supply is not None else None),
        "days_of_supply": (round(weeks_of_supply * 7, 0) if weeks_of_supply is not None else None),
        "sell_through_rate": round(sell_through, 3),
        "turnover": (round(turnover, 2) if turnover is not None else None),
        "cash_frozen": round(cash if stock_class in FROZEN_CLASSES else 0.0, 2),
        "inventory_value": round(cash, 2),
        "money_at_stake": round(money_at_stake, 2),
        "stock_class": stock_class,
        "stock_label": CLASS_LABELS[stock_class],
        "health_score": round(min(max(health, 0.0), 100.0), 1),
        "opportunity_score": round(min(max(opportunity, 0.0), 100.0), 1),
    }


def _percentiles(values: list[float]) -> dict:
    """Value → percentile rank (0-1). Ties share the same rank."""
    if not values:
        return {}
    ordered = sorted(set(values))
    last = len(ordered) - 1 or 1
    return {v: i / last for i, v in enumerate(ordered)}


def compute_all(products: list[dict], period_days: int) -> list[dict]:
    """
    Enrich a whole store in one pass.

    Percentiles and the largest frozen position are store-relative, so they are
    computed here once rather than per product — "a big position" only means
    anything next to this store's other positions.
    """
    if not products:
        return []

    revenues = [_num(p.get("total_amount")) for p in products]
    units = [_num(p.get("quantity")) for p in products]
    rev_pct, unit_pct = _percentiles(revenues), _percentiles(units)

    # First pass with no scaling, to find the largest money-at-stake position.
    provisional = [compute(p, period_days) for p in products]
    max_cash = max((r["money_at_stake"] for r in provisional), default=0.0)

    return [
        compute(
            p, period_days,
            max_cash=max_cash,
            revenue_percentile=rev_pct.get(_num(p.get("total_amount")), 0.5),
            units_percentile=unit_pct.get(_num(p.get("quantity")), 0.5),
        )
        for p in products
    ]


def summarise(metrics: list[dict], period_days: int) -> dict:
    """Store-level rollup: the numbers the Action Center and health score need."""
    if not metrics:
        return {
            "products": 0, "inventory_value": 0.0, "cash_frozen": 0.0,
            "revenue": 0.0, "units": 0.0, "turnover": None,
            "sell_through_rate": 0.0, "by_class": {}, "by_category": {},
        }

    inventory_value = sum(m["inventory_value"] for m in metrics)
    cash_frozen = sum(m["cash_frozen"] for m in metrics)
    revenue = sum(m["revenue"] for m in metrics)
    units = sum(m["units_sold"] for m in metrics)
    stock_units = sum(m["stock"] for m in metrics if m["stock"] > 0)

    periods_per_year = 365.0 / max(1, period_days)
    turnover = ((revenue * periods_per_year) / inventory_value) if inventory_value > 0 else None

    by_class: dict[str, dict] = {}
    for m in metrics:
        entry = by_class.setdefault(m["stock_class"], {"count": 0, "value": 0.0})
        entry["count"] += 1
        entry["value"] = round(entry["value"] + m["inventory_value"], 2)

    by_category: dict[str, dict] = {}
    for m in metrics:
        key = m.get("category") or "Other"
        entry = by_category.setdefault(
            key, {"count": 0, "inventory_value": 0.0, "revenue": 0.0, "cash_frozen": 0.0})
        entry["count"] += 1
        entry["inventory_value"] = round(entry["inventory_value"] + m["inventory_value"], 2)
        entry["revenue"] = round(entry["revenue"] + m["revenue"], 2)
        entry["cash_frozen"] = round(entry["cash_frozen"] + m["cash_frozen"], 2)

    return {
        "products": len(metrics),
        "inventory_value": round(inventory_value, 2),
        "cash_frozen": round(cash_frozen, 2),
        "frozen_pct": round(cash_frozen / inventory_value * 100, 1) if inventory_value else 0.0,
        "revenue": round(revenue, 2),
        "units": round(units, 2),
        "turnover": round(turnover, 2) if turnover is not None else None,
        "sell_through_rate": round(units / (units + stock_units), 3) if (units + stock_units) else 0.0,
        "by_class": by_class,
        "by_category": by_category,
        "period_days": period_days,
    }
