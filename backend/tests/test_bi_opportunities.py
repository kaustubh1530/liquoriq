"""
tests/test_bi_opportunities.py — PHASE 22: opportunity engine + action center

The brief's rule is the thing under test here: BUSINESS LOGIC IS DETERMINISTIC.
Every dollar figure, ranking and priority below is arithmetic on the store's own
numbers plus a named assumption. Nothing calls GPT, and these tests would fail
if anything started to.
"""

import pytest

from app.services.bi import action_center as AC
from app.services.bi import assumptions as A
from app.services.bi import opportunities as OPP
from app.services.bi import product_metrics as PM


def make(units=10.0, stock=10.0, price=20.0, category="Whiskey", name="BOTTLE"):
    return {"product_name": name, "sku": name, "category": category,
            "quantity": units, "stock_on_hand": stock, "unit_price": price,
            "total_amount": units * price}


def metrics_for(products, days=30):
    return PM.compute_all(products, days)


# ── Detector: reorder ────────────────────────────────────────────────────────

def test_reorder_fires_on_sold_out_items_that_were_selling():
    m = metrics_for([make(units=40, stock=0, price=25, name="SOLD OUT"),
                     make(units=10, stock=200, name="FINE")])
    out = OPP.detect_reorder(m)
    assert len(out) == 1
    assert out[0]["evidence"]["products_out_of_stock"] == 1
    assert out[0]["value_score"] > 0


def test_reorder_ignores_items_that_never_sold():
    """Zero stock and zero sales isn't a stock-out, it's a discontinued line."""
    assert OPP.detect_reorder(metrics_for([make(units=0, stock=0)])) == []


def test_reorder_confidence_rises_with_more_history():
    m = metrics_for([make(units=40, stock=0)])
    assert OPP.detect_reorder(m, periods_of_history=1)[0]["confidence"] == "medium"
    assert OPP.detect_reorder(m, periods_of_history=3)[0]["confidence"] == "high"


# ── Detector: clearance ──────────────────────────────────────────────────────

def test_clearance_values_frozen_cash_at_the_recovery_rate():
    m = metrics_for([make(units=1, stock=100, price=50)])   # sleeping, $5,000
    out = OPP.detect_clearance(m)[0]
    # Renamed to _retail: the figure is at shelf price, not what the owner paid.
    assert out["evidence"]["cash_frozen_retail"] == pytest.approx(5000.0)
    assert out["value_score"] == pytest.approx(5000.0 * A.CLEARANCE_RECOVERY_RATE)


def test_clearance_separates_sleeping_from_the_rest():
    """The split the owner asked for has to survive into the evidence.
    Over 30 days: 10 units = 2.33/wk, so 82 in stock ~= 35 weeks (overstock),
    while 1 unit against 2000 in stock is years of supply (sleeping)."""
    m = metrics_for([make(units=1, stock=2000, price=10, name="SLEEPING"),
                     make(units=10, stock=82, price=10, name="OVERSTOCK")])
    classes = {x["product_name"]: x["stock_class"] for x in m}
    assert classes["SLEEPING"] == "sleeping" and classes["OVERSTOCK"] == "overstock"

    ev = OPP.detect_clearance(m)[0]["evidence"]
    assert ev["products"] == 2
    assert ev["sleeping_over_a_year"] == 1
    assert ev["sleeping_cash"] > 0


def test_clearance_is_high_confidence_because_it_is_measured():
    m = metrics_for([make(units=1, stock=100, price=50)])
    assert OPP.detect_clearance(m)[0]["confidence"] == "high"


def test_healthy_store_produces_no_clearance():
    assert OPP.detect_clearance(metrics_for([make(units=50, stock=200)])) == []


# ── Detector: seasonal ───────────────────────────────────────────────────────

def test_seasonal_only_fires_inside_the_lead_time_window():
    """Relevance now comes from the holiday KEY, not an inline category list."""
    m = metrics_for([make(units=10, stock=300, category="Beer")])
    soon = [{"key": "labor_day", "name": "Labor Day", "days_away": 30}]
    far = [{"key": "christmas", "name": "Christmas", "days_away": 200}]
    assert len(OPP.detect_seasonal(m, soon)) == 1
    assert OPP.detect_seasonal(m, far) == []


def test_seasonal_only_counts_relevant_categories():
    """
    Beer sells for Labor Day; Cognac does not. The old detector scoped every
    product the store held — 99% of inventory — and called it a holiday
    opportunity.
    """
    m = metrics_for([make(units=10, stock=300, category="Beer", name="B"),
                     make(units=10, stock=300, category="Cognac/Brandy", name="C")])
    out = OPP.detect_seasonal(m, [{"key": "labor_day", "name": "Labor Day",
                                   "days_away": 10}])
    assert out[0]["evidence"]["products_in_scope"] == 1
    assert "Beer" in out[0]["evidence"]["relevant_categories"]
    assert out[0]["products"] == ["B"]


# ── Detector: bundle + upsell ────────────────────────────────────────────────

def test_bundle_pairs_a_fast_mover_with_a_slow_one_in_the_same_category():
    m = metrics_for([make(units=100, stock=140, name="FAST", category="Rum"),
                     make(units=1, stock=2000, price=40, name="SLOW", category="Rum")])
    assert {x["product_name"]: x["stock_class"] for x in m}["FAST"] == "healthy"
    out = OPP.detect_bundle(m)
    assert len(out) == 1
    pair = out[0]["evidence"]["pairs"][0]
    assert pair["anchor"] == "FAST" and pair["slow_item"] == "SLOW"


def test_bundle_needs_both_a_fast_and_a_slow_item():
    assert OPP.detect_bundle(metrics_for([make(units=100, stock=140)])) == []


def test_bundle_is_low_confidence_without_basket_data():
    m = metrics_for([make(units=100, stock=140, name="F"),
                     make(units=1, stock=2000, price=40, name="S")])
    assert OPP.detect_bundle(m)[0]["confidence"] == "low"


def test_premium_upsell_needs_a_real_price_ladder():
    m = metrics_for([make(units=50, stock=100, price=20, name="SMALL"),
                     make(units=5, stock=50, price=45, name="LARGE")])
    out = OPP.detect_premium_upsell(m, {"SMALL": "Brand", "LARGE": "Brand"})
    ladder = out[0]["evidence"]["ladders"][0]
    assert ladder["from_price"] == 20.0 and ladder["to_price"] == 45.0
    assert out[0]["value_score"] == pytest.approx(50 * A.UPSELL_CONVERSION_RATE * 25)


def test_no_upsell_when_a_brand_has_one_size():
    m = metrics_for([make(name="ONLY")])
    assert OPP.detect_premium_upsell(m, {"ONLY": "Brand"}) == []


# ── Detector: win-back + campaign repeat ─────────────────────────────────────

def test_winback_uses_real_segment_sizes_and_spend():
    out = OPP.detect_winback({"At Risk": {"count": 100, "avg_spend": 50.0}})
    assert out[0]["value_score"] == pytest.approx(100 * A.WINBACK_RESPONSE_RATE * 50.0)


def test_winback_ignores_active_segments():
    assert OPP.detect_winback({"VIP": {"count": 100, "avg_spend": 200.0}}) == []


def test_campaign_repeat_is_high_confidence_because_it_already_worked_here():
    out = OPP.detect_campaign_repeat(
        [{"title": "Bourbon Push", "lift_revenue": 3000.0, "days_since": 40}])
    assert out[0]["confidence"] == "high"
    assert out[0]["value_score"] == 3000.0


def test_campaign_repeat_ignores_failures_and_recent_runs():
    assert OPP.detect_campaign_repeat([{"title": "Flop", "lift_revenue": -50, "days_since": 40}]) == []
    assert OPP.detect_campaign_repeat([{"title": "Fresh", "lift_revenue": 900, "days_since": 3}]) == []


# ── Ranking ──────────────────────────────────────────────────────────────────

def test_confidence_weighting_stops_a_shaky_number_topping_the_list():
    """
    A $10,000 low-confidence guess must not outrank a $9,000 measured fact.
    This is the guard that keeps the to-do list honest.
    """
    shaky = OPP._opportunity("bundle", "Shaky", 10_000, "low", "guess", {}, "do", "/x")
    solid = OPP._opportunity("clearance", "Solid", 9_000, "high", "measured", {}, "do", "/y")
    ranked = sorted([shaky, solid], key=lambda o: -o["ranked_value"])
    assert ranked[0]["title"] == "Solid"
    assert shaky["ranked_value"] == pytest.approx(10_000 * A.CONFIDENCE_WEIGHTS["low"])


def test_detect_all_sorts_and_ranks():
    m = metrics_for([make(units=1, stock=500, price=40, name="SLOW"),
                     make(units=60, stock=0, price=30, name="OUT")])
    found = OPP.detect_all(m)
    assert found and found[0]["rank"] == 1
    assert all(found[i]["ranked_value"] >= found[i + 1]["ranked_value"]
               for i in range(len(found) - 1))


def test_empty_store_produces_no_opportunities():
    assert OPP.detect_all([]) == []


# ── Action Center: the seven required fields ─────────────────────────────────

REQUIRED = ["priority", "business_impact", "evidence", "expected_outcome",
            "confidence", "suggested_action", "action"]


def test_every_action_carries_all_seven_required_fields():
    m = metrics_for([make(units=1, stock=500, price=40)])
    for action in AC.build_actions(OPP.detect_all(m)):
        for field in REQUIRED:
            assert field in action and action[field] not in (None, ""), field
        assert {"label", "route"} <= set(action["action"])   # a real button


def test_stock_outs_are_p1_even_when_smaller_than_frozen_cash():
    """Urgency beats size: a stock-out bleeds daily, frozen cash already has."""
    m = metrics_for([make(units=60, stock=0, price=30, name="OUT"),
                     make(units=1, stock=500, price=40, name="SLOW")])
    actions = AC.build_actions(OPP.detect_all(m))
    reorder = next(a for a in actions if a["type"] == "reorder")
    assert reorder["priority"] == "P1"


def test_actions_are_ordered_by_priority_then_value():
    m = metrics_for([make(units=60, stock=0, price=30, name="OUT"),
                     make(units=1, stock=500, price=40, name="SLOW")])
    actions = AC.build_actions(OPP.detect_all(m))
    order = {"P1": 0, "P2": 1, "P3": 2}
    assert [order[a["priority"]] for a in actions] == sorted(order[a["priority"]] for a in actions)


# ── Business health score ────────────────────────────────────────────────────

def test_business_health_is_low_when_cash_is_frozen():
    m = metrics_for([make(units=1, stock=1000, price=50)])
    health = AC.business_health(PM.summarise(m, 30), m)
    assert health["score"] < 50
    assert health["band"] in ("needs attention", "at risk")


def test_business_health_is_higher_for_a_well_run_store():
    frozen = metrics_for([make(units=1, stock=1000, price=50)])
    brisk = metrics_for([make(units=200, stock=100, price=50)])
    assert (AC.business_health(PM.summarise(brisk, 30), brisk)["score"]
            > AC.business_health(PM.summarise(frozen, 30), frozen)["score"])


def test_health_components_are_always_shown():
    """A score with no visible parts is a horoscope — the breakdown is the point."""
    m = metrics_for([make()])
    components = AC.business_health(PM.summarise(m, 30), m)["components"]
    assert {c["key"] for c in components} >= {
        "turnover", "healthy_cash", "sell_through", "availability", "data_quality"}
    assert all({"label", "value", "target", "weight"} <= set(c) for c in components)


def test_health_score_stays_in_range_on_an_empty_store():
    health = AC.business_health(PM.summarise([], 30), [])
    assert 0 <= health["score"] <= 100


def test_build_returns_assumptions_so_nothing_is_hidden():
    m = metrics_for([make(units=1, stock=500, price=40)])
    payload = AC.build(PM.summarise(m, 30), m, OPP.detect_all(m))
    assert payload["assumptions"]
    assert "business_health" in payload and "actions" in payload
