"""
services/bi/assumptions.py — PHASE 22: every assumption in ONE place

Why this file exists: the POS export has NO COST DATA, so any statement about
profit is an assumption, not a fact. Rather than bury guesses inside formulas,
every threshold and rate lives here, is labelled, and is quoted back to the
owner in the UI as an assumption they can change.

If a number appears anywhere in the BI engine and isn't derived from the store's
own data, it is defined here or it is a bug.
"""

# ── Stock classification thresholds (weeks of supply) ────────────────────────
# Calibrated against the pilot store's real July file (1,403 products).
# The old code used a single >16-week "overstock" bucket, which flagged 466
# products with no ranking — an unusable to-do list. Splitting at 52 weeks
# isolates the products whose cash is genuinely gone.
CRITICAL_WEEKS = 1.0      # < 1 week  → stock-out imminent
REORDER_WEEKS = 3.0       # < 3 weeks → order this week
HEALTHY_MAX_WEEKS = 12.0  # 3–12      → the target band, leave alone
HEAVY_MAX_WEEKS = 26.0    # 12–26     → watch
OVERSTOCK_MAX_WEEKS = 52.0  # 26–52   → promote;  > 52 → "sleeping", clearance

# ── Inventory turnover benchmark (times per year) ────────────────────────────
# Independent liquor retail typically turns 4–6x. Used to score the store, and
# to size the "trapped cash" figure against what good would look like.
TURNOVER_BENCHMARK_LOW = 4.0
TURNOVER_BENCHMARK_HIGH = 6.0

# ── Gross margin by category (industry-typical; owner-editable) ──────────────
# ONLY used to translate revenue into estimated profit. Never used to compute
# inventory value — that is always stated at retail, which we DO know.
CATEGORY_MARGINS: dict[str, float] = {
    "Whiskey": 0.30, "Vodka": 0.30, "Tequila": 0.30, "Rum": 0.30, "Gin": 0.30,
    "Cognac/Brandy": 0.32, "Liqueur": 0.32, "Wine": 0.33, "Champagne": 0.35,
    "Beer": 0.22, "Seltzer/RTD": 0.25, "Non-alcoholic": 0.40, "Tobacco": 0.12,
    "Other": 0.28,
}
DEFAULT_MARGIN = 0.28

# ── Recovery / response rates used to size opportunities ─────────────────────
CLEARANCE_RECOVERY_RATE = 0.60   # a clearance realises ~60% of retail value
HOLIDAY_UPLIFT_RATE = 0.15       # a well-timed seasonal push moves ~15% of
                                 # the relevant category's stock value
WINBACK_RESPONSE_RATE = 0.08     # ~8% of a contacted lapsed segment returns
BUNDLE_ATTACH_RATE = 0.12        # ~12% of buyers of A also take B when bundled
UPSELL_CONVERSION_RATE = 0.10    # ~10% trade up when prompted at the shelf
REORDER_HORIZON_WEEKS = 4.0      # value a stock-out as 4 weeks of lost sales

# ── Confidence weighting ─────────────────────────────────────────────────────
# Applied to an opportunity's dollar value before ranking, so a large but shaky
# estimate cannot outrank a smaller, well-evidenced one.
CONFIDENCE_WEIGHTS = {"high": 1.0, "medium": 0.7, "low": 0.4}

# How much history we need before a trend-based claim is "high" confidence.
HIGH_CONFIDENCE_PERIODS = 2

# ── Product opportunity score weights (must sum to 1.0) ──────────────────────
OPP_WEIGHT_MONEY = 0.50      # cash at stake, relative to the store's biggest
OPP_WEIGHT_URGENCY = 0.30    # from the stock class
OPP_WEIGHT_DEMAND = 0.20     # units-sold percentile

# ── Product health score weights (must sum to 1.0) ───────────────────────────
HEALTH_WEIGHT_SUPPLY = 0.40
HEALTH_WEIGHT_SELLTHROUGH = 0.30
HEALTH_WEIGHT_REVENUE = 0.20
HEALTH_WEIGHT_AVAILABILITY = 0.10

# ── Business health score weights (must sum to 1.0) ──────────────────────────
BIZ_WEIGHT_TURNOVER = 0.35
BIZ_WEIGHT_HEALTHY_CASH = 0.25
BIZ_WEIGHT_SELLTHROUGH = 0.20
BIZ_WEIGHT_AVAILABILITY = 0.10
BIZ_WEIGHT_DATA_QUALITY = 0.10

# ── Fallbacks ────────────────────────────────────────────────────────────────
DEFAULT_PERIOD_DAYS = 30

# Gross margin is NEVER assumed. The POS export has no cost data, so unless the
# owner tells us his margin every inventory figure stays at retail and is
# labelled as such. An industry average dressed up as his number is exactly the
# kind of plausible-looking fiction this engine exists to avoid.
GROSS_MARGIN_MIN = 1
GROSS_MARGIN_MAX = 90

# How much extra revenue one month of clearance can realistically produce, as a
# share of a normal month's sales. A clearance competes with normal trade for
# the same customers and the same shelf space, so "free up $132,396" — two
# months of this store's ENTIRE revenue — is not a thing that happens in a
# week. Used to phase large clearances. ASSUMPTION, reported as one.
CLEARANCE_CAPACITY_PCT = 0.15     # only when a file states no reporting period


def margin_for(category: str | None) -> float:
    """Assumed gross margin for a category. Never a measured fact."""
    return CATEGORY_MARGINS.get(category or "", DEFAULT_MARGIN)


def as_disclosure() -> list[dict]:
    """
    The assumptions, formatted for display. The UI shows these next to any
    figure derived from them so the owner can see exactly what was assumed
    rather than trusting a number that looks precise.
    """
    return [
        {"key": "clearance_recovery", "label": "Clearance recovers",
         "value": f"{CLEARANCE_RECOVERY_RATE:.0%} of retail value",
         "why": "A discounted bottle sells below shelf price. The frozen amount "
                "itself is measured; this rate is not."},
        {"key": "clearance_capacity", "label": "A clearance can add",
         "value": f"{CLEARANCE_CAPACITY_PCT:.0%} to a normal month's sales",
         "why": "Used to phase large clearances. A clearance competes with normal "
                "trade, so it cannot all happen at once."},
        {"key": "holiday_uplift", "label": "Holiday lift",
         "value": "8–35% of what the relevant products already sell, per holiday",
         "why": "Applied ONLY to the categories that move for that holiday, and "
                "capped by stock on hand. Industry figures, not this store's own "
                "holiday history — replace once several years of reports exist."},
        {"key": "winback_response", "label": "Win-back response",
         "value": f"{WINBACK_RESPONSE_RATE:.0%} of those contacted",
         "why": "Typical direct-marketing response. The segment sizes and past "
                "spend behind it are real."},
        {"key": "bundle_attach", "label": "Bundle attach rate",
         "value": f"{BUNDLE_ATTACH_RATE:.0%}",
         "why": "The POS export has no basket-level data, so this cannot yet be "
                "measured from the store's own transactions."},
        {"key": "upsell_conversion", "label": "Upsell conversion",
         "value": f"{UPSELL_CONVERSION_RATE:.0%}",
         "why": "The price gaps are real; the share of customers who trade up is not."},
        {"key": "reorder_horizon", "label": "Stock-out costs",
         "value": f"{REORDER_HORIZON_WEEKS:.0f} weeks of lost sales",
         "why": "How far ahead a reorder is valued. Longer horizons produce "
                "bigger figures without more evidence."},
        {"key": "turnover_benchmark", "label": "Healthy turnover",
         "value": f"{TURNOVER_BENCHMARK_LOW:.0f}–{TURNOVER_BENCHMARK_HIGH:.0f}x per year",
         "why": "An industry benchmark used as a target, not a measurement of "
                "this store."},
        {"key": "margins", "label": "Cost of goods",
         "value": "unknown unless the owner supplies a gross margin",
         "why": "The POS export carries selling prices only. Until a margin is "
                "entered, every inventory figure is at RETAIL and labelled so."},
    ]


# Guard rails: a typo in a weight would silently skew every score.
assert abs(OPP_WEIGHT_MONEY + OPP_WEIGHT_URGENCY + OPP_WEIGHT_DEMAND - 1.0) < 1e-9
assert abs(HEALTH_WEIGHT_SUPPLY + HEALTH_WEIGHT_SELLTHROUGH
           + HEALTH_WEIGHT_REVENUE + HEALTH_WEIGHT_AVAILABILITY - 1.0) < 1e-9
assert abs(BIZ_WEIGHT_TURNOVER + BIZ_WEIGHT_HEALTHY_CASH + BIZ_WEIGHT_SELLTHROUGH
           + BIZ_WEIGHT_AVAILABILITY + BIZ_WEIGHT_DATA_QUALITY - 1.0) < 1e-9
assert CRITICAL_WEEKS < REORDER_WEEKS < HEALTHY_MAX_WEEKS < HEAVY_MAX_WEEKS < OVERSTOCK_MAX_WEEKS
