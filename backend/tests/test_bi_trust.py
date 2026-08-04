"""
tests/test_bi_trust.py — the three fixes that make the numbers defensible.

Everything here traces to a figure the dashboard actually showed a real store
owner and could not justify:

  1. "$191,074 on the table" summed Clearance and Seasonal, which named the
     same 18 of 20 products. You cannot dump a bottle at 60% clearance AND
     sell it at a holiday markup — that's a choice presented as a sum.

  2. "Labor Day · stock in scope $310,591" was 99% of the entire inventory.
     Nobody buys Cognac for a barbecue.

  3. "P1 · Do this now · free up $132,396" was two months of the store's
     ENTIRE revenue, with no timeframe.
"""

import pytest

from app.services.bi import assumptions as A
from app.services.bi import opportunities as OPP
from app.services.bi import planning as PLAN
from app.services.bi import product_metrics as PM
from app.services.bi import seasonality as SEASON


def make(name, category, units, stock, price):
    return {"product_name": name, "sku": name, "category": category,
            "quantity": units, "unit_price": price,
            "total_amount": units * price, "stock_on_hand": stock}


def metrics(rows, days=31):
    return PM.compute_all(rows, days)


# ═══ 1. One product, one primary action ══════════════════════════════════════

SLOW_BEER = make("SUMMER LAGER 12PK", "Beer", 2, 400, 15.0)     # sleeping + Labor Day
LABOR_DAY = [{"key": "labor_day", "name": "Labor Day Weekend", "days_away": 28}]


def test_a_product_cannot_be_counted_by_two_opportunities():
    m = metrics([SLOW_BEER])
    found = OPP.detect_all(m, holidays=LABOR_DAY, period_days=31)

    owners = [o["type"] for o in found
              if SLOW_BEER["product_name"] in (o.get("product_values") or {})]
    assert len(owners) == 1, f"counted by {owners}"


def test_the_headline_total_is_not_inflated_by_overlap():
    """The sum is only meaningful once each product has a single owner."""
    m = metrics([SLOW_BEER])
    raw = (OPP.detect_clearance(m)[0]["value_score"]
           + OPP.detect_seasonal(m, LABOR_DAY)[0]["value_score"])
    allocated = OPP.total_value(OPP.detect_all(m, holidays=LABOR_DAY, period_days=31))
    assert allocated["raw"] < raw


def test_the_product_goes_to_whichever_action_values_it_most():
    m = metrics([SLOW_BEER])
    clearance = OPP.detect_clearance(m)[0]["product_values"][SLOW_BEER["product_name"]]
    seasonal = OPP.detect_seasonal(m, LABOR_DAY)[0]["product_values"][SLOW_BEER["product_name"]]
    winner = "clearance" if clearance > seasonal else "seasonal"

    found = OPP.detect_all(m, holidays=LABOR_DAY, period_days=31)
    owner = next(o["type"] for o in found
                 if SLOW_BEER["product_name"] in (o.get("product_values") or {}))
    assert owner == winner


def test_customer_led_opportunities_are_exempt():
    """A win-back mailing and a clearance can run on the same bottle."""
    segments = {"At Risk": {"count": 40, "avg_spend": 90.0}}
    found = OPP.detect_all(metrics([SLOW_BEER]), holidays=LABOR_DAY,
                           segments=segments, period_days=31)
    assert any(o["type"] == "winback" for o in found)


def test_an_opportunity_that_loses_every_product_is_dropped():
    opportunities = [
        {"type": "clearance", "product_values": {"X": 100.0}, "products": ["X"],
         "confidence_weight": 1.0, "value_score": 100.0, "ranked_value": 100.0},
        {"type": "seasonal", "product_values": {"X": 10.0}, "products": ["X"],
         "confidence_weight": 0.7, "value_score": 10.0, "ranked_value": 7.0},
    ]
    out = OPP.allocate_exclusively(opportunities)
    assert [o["type"] for o in out] == ["clearance"]


def test_yielding_products_is_disclosed_not_silent():
    opportunities = [
        {"type": "clearance", "product_values": {"X": 100.0, "Y": 50.0},
         "products": ["X", "Y"], "confidence_weight": 1.0,
         "value_score": 150.0, "ranked_value": 150.0},
        {"type": "seasonal", "product_values": {"X": 500.0, "Z": 5.0},
         "products": ["X", "Z"], "confidence_weight": 1.0,
         "value_score": 505.0, "ranked_value": 505.0},
    ]
    out = {o["type"]: o for o in OPP.allocate_exclusively(opportunities)}
    assert out["clearance"]["products_yielded"] == 1
    assert "not counted twice" in out["clearance"]["allocation_note"]
    assert out["clearance"]["value_score"] == pytest.approx(50.0)


def test_allocation_is_deterministic_across_runs():
    m = metrics([SLOW_BEER])
    runs = [tuple((o["type"], o["value_score"])
                  for o in OPP.detect_all(m, holidays=LABOR_DAY, period_days=31))
            for _ in range(5)]
    assert len(set(runs)) == 1


# ═══ 2. Seasonal relevance ═══════════════════════════════════════════════════

SHOP = [
    make("SUMMER LAGER 12PK", "Beer", 40, 100, 15.0),
    make("HARD SELTZER VARIETY", "Seltzer/RTD", 30, 80, 18.0),
    make("BLANCO TEQUILA 750", "Tequila", 20, 40, 28.0),
    make("HENNESSY VS 750", "Cognac/Brandy", 15, 30, 45.0),
    make("VINTAGE PORT 750", "Wine", 5, 20, 60.0),
    make("SINGLE MALT SCOTCH", "Whiskey", 8, 25, 90.0),
]


def test_a_barbecue_holiday_does_not_scope_cognac():
    qualified = SEASON.qualify(metrics(SHOP), "labor_day", "Labor Day Weekend")
    names = {q["product_name"] for q in qualified}
    assert "HENNESSY VS 750" not in names
    assert "SINGLE MALT SCOTCH" not in names
    assert "SUMMER LAGER 12PK" in names


def test_scope_is_a_minority_of_the_shop_not_all_of_it():
    qualified = SEASON.qualify(metrics(SHOP), "labor_day", "Labor Day Weekend")
    assert len(qualified) < len(SHOP)


def test_every_qualifying_product_explains_itself():
    for q in SEASON.qualify(metrics(SHOP), "labor_day", "Labor Day Weekend"):
        assert q["qualified_because"]
        assert q["qualified_by"] in ("category", "keyword")


def test_a_keyword_qualifies_what_a_category_cannot():
    """St Patrick's is IRISH whiskey, not every whiskey in the shop."""
    rows = [make("JAMESON IRISH 750", "Whiskey", 10, 20, 30.0),
            make("JAPANESE MALT 750", "Sake/Soju", 10, 20, 60.0)]
    qualified = SEASON.qualify(metrics(rows), "st_patricks", "St. Patrick's Day")
    names = {q["product_name"] for q in qualified}
    assert "JAMESON IRISH 750" in names


def test_sold_out_products_are_never_promoted():
    """Driving demand you can't serve is worse than staying quiet."""
    rows = [make("SUMMER LAGER 12PK", "Beer", 40, 0, 15.0)]
    assert SEASON.qualify(metrics(rows), "labor_day", "Labor Day") == []


def test_the_uplift_is_based_on_sales_not_on_shelf_stock():
    """
    The old model took 15% of STOCK VALUE, so hoarding dead inventory inflated
    the opportunity. The lift now applies to what these products actually sold.
    """
    qualified = SEASON.qualify(metrics(SHOP), "labor_day", "Labor Day Weekend")
    uplift = SEASON.expected_uplift(qualified, "labor_day")
    expected = uplift["base_revenue"] * uplift["lift_rate"]
    assert uplift["value"] == pytest.approx(min(expected, uplift["stock_value"]))


def test_the_uplift_cannot_exceed_the_stock_on_hand():
    rows = [make("SUMMER LAGER 12PK", "Beer", 1000, 1, 15.0)]
    uplift = SEASON.expected_uplift(
        SEASON.qualify(metrics(rows), "labor_day", "Labor Day"), "labor_day")
    assert uplift["value"] <= uplift["stock_value"]
    assert uplift["capped_by_stock"] is True


def test_an_unknown_holiday_under_claims_rather_than_scoping_everything():
    qualified = SEASON.qualify(metrics(SHOP), "not_a_real_holiday", "Mystery Day")
    assert qualified == []


def test_every_rule_names_only_real_categories():
    from app.services.bi import categorizer as CAT
    for key, rule in SEASON.HOLIDAY_RULES.items():
        for category in rule["categories"]:
            assert category in CAT.CATEGORIES, f"{key} references unknown {category!r}"


def test_every_rule_has_a_plausible_lift():
    for key, rule in SEASON.HOLIDAY_RULES.items():
        assert 0 < rule["lift"] <= 0.5, f"{key} claims an implausible lift"


# ═══ 3. Execution planning ═══════════════════════════════════════════════════

def test_every_opportunity_carries_a_timeline():
    found = OPP.detect_all(metrics(SHOP), holidays=LABOR_DAY,
                           segments={"At Risk": {"count": 10, "avg_spend": 50.0}},
                           period_days=31)
    assert found
    for o in found:
        assert o["timeline"], o["type"]
        assert o["timeline_reason"], o["type"]


def test_a_stock_out_is_todays_problem():
    out = PLAN.timeline_for("reorder", {"products_out_of_stock": 115})
    assert out["timeline"] == "Today"
    assert "can't get back" in out["timeline_reason"]


def test_a_holiday_is_dated_by_the_holiday():
    out = PLAN.timeline_for("seasonal", {"days_away": 28, "holiday": "Labor Day Weekend"})
    assert out["timeline"] == "Before Labor Day Weekend"
    assert "21 days" in out["timeline_reason"]   # 28 minus a week of lead time


def test_a_large_clearance_is_never_do_this_now():
    assert PLAN.timeline_for("clearance")["timeline"] == "This quarter"


def test_the_clearance_becomes_a_phased_plan():
    stuck = [m for m in metrics(SHOP + [make(f"DEAD {i}", "Wine", 0, 50, 40.0)
                                        for i in range(30)])
             if m["cash_frozen"] > 0]
    plan = PLAN.clearance_phases(stuck, period_revenue=66753.0, period_days=31)
    assert 1 <= len(plan["phases"]) <= 3
    assert plan["months_to_clear"] >= 1
    assert all(p["products"] > 0 for p in plan["phases"])


def test_every_stuck_product_lands_in_exactly_one_phase():
    stuck = [m for m in metrics([make(f"DEAD {i}", "Wine", 0, 50, 40.0)
                                 for i in range(25)]) if m["cash_frozen"] > 0]
    plan = PLAN.clearance_phases(stuck, 66753.0, 31)
    assert sum(p["products"] for p in plan["phases"]) == len(stuck)


def test_the_phase_plan_is_sized_against_the_stores_own_revenue():
    stuck = [m for m in metrics([make(f"DEAD {i}", "Wine", 0, 50, 40.0)
                                 for i in range(25)]) if m["cash_frozen"] > 0]
    small = PLAN.clearance_phases(stuck, 10_000.0, 31)
    large = PLAN.clearance_phases(stuck, 200_000.0, 31)
    assert small["months_to_clear"] > large["months_to_clear"]


def test_the_capacity_assumption_is_disclosed():
    stuck = [m for m in metrics([make("DEAD", "Wine", 0, 50, 40.0)])
             if m["cash_frozen"] > 0]
    basis = PLAN.clearance_phases(stuck, 66753.0, 31)["basis"]
    assert "assumption" in basis.lower()
    assert f"{A.CLEARANCE_CAPACITY_PCT:.0%}" in basis


def test_an_empty_clearance_does_not_divide_by_zero():
    assert PLAN.clearance_phases([], 0.0, 31)["phases"] == []


# ═══ 4. Assumptions are never presented as facts ═════════════════════════════

def test_assumption_backed_opportunities_are_flagged_as_estimates():
    found = OPP.detect_all(metrics(SHOP), holidays=LABOR_DAY, period_days=31)
    for o in found:
        assert "estimated" in o


def test_the_clearance_confidence_reason_separates_measured_from_assumed():
    out = OPP.detect_clearance(metrics(SHOP + [SLOW_BEER]), 66753.0, 31)[0]
    reason = out["confidence_reason"]
    assert "measured" in reason and "assumption" in reason


def test_the_seasonal_reason_admits_the_uplift_is_not_measured():
    out = OPP.detect_seasonal(metrics(SHOP), LABOR_DAY)[0]
    assert "assumption" in out["confidence_reason"]
    assert "not" in out["confidence_reason"]


def test_the_totals_state_that_they_are_not_double_counted():
    total = OPP.total_value(OPP.detect_all(metrics(SHOP), holidays=LABOR_DAY,
                                           period_days=31))
    assert "one opportunity only" in total["basis"]
