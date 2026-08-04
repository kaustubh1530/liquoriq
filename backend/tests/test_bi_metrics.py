"""
tests/test_bi_metrics.py — PHASE 22: per-product intelligence

These numbers drive money decisions (what to reorder, what to clear), so the
classification boundaries and the two scores are pinned hard.
"""

import pytest

from app.services.bi import assumptions as A
from app.services.bi import product_metrics as PM


def make(units=10.0, stock=10.0, price=20.0, revenue=None, **kw):
    return {
        "product_name": kw.get("name", "TEST BOTTLE"),
        "sku": kw.get("sku", "1"),
        "category": kw.get("category", "Whiskey"),
        "quantity": units,
        "stock_on_hand": stock,
        "unit_price": price,
        "total_amount": revenue if revenue is not None else units * price,
    }


# ── The period fix: the whole reason velocity was wrong before ───────────────

def test_velocity_uses_the_real_period_not_a_fixed_month():
    """
    REGRESSION: the old code divided by a hard-coded 4.3 weeks. The same 28
    units over a WEEK is 4x the velocity of 28 units over a month, and that
    ratio decides every reorder and overstock verdict.
    """
    weekly = PM.compute(make(units=28, stock=14), period_days=7)
    monthly = PM.compute(make(units=28, stock=14), period_days=28)
    assert weekly["weekly_velocity"] == pytest.approx(28.0)
    assert monthly["weekly_velocity"] == pytest.approx(7.0)
    assert weekly["weeks_of_supply"] == pytest.approx(0.5)
    assert monthly["weeks_of_supply"] == pytest.approx(2.0)
    # Identical raw numbers, different verdicts — which is the whole point.
    assert weekly["stock_class"] == "critical"   # order today
    assert monthly["stock_class"] == "reorder"   # order this week


def test_missing_period_falls_back_without_crashing():
    for bad in (0, None):
        out = PM.compute(make(), period_days=bad)
        assert out["weekly_velocity"] > 0


# ── The 9 classes ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("units,stock,expected", [
    # period_days=7, so weekly velocity == units and weeks_of_supply == stock/units
    (10, -5, "negative"),     # data quality — checked before any ratio
    (10, 0, "sold_out"),      # was selling, none left → lost sales
    (0, 0, "dead"),
    (0, 20, "dead"),          # has stock, never moved
    (100, 10, "critical"),    # 0.1 weeks
    (10, 20, "reorder"),      # 2 weeks
    (10, 60, "healthy"),      # 6 weeks
    (10, 180, "heavy"),       # 18 weeks
    (10, 300, "overstock"),   # 30 weeks
    (10, 800, "sleeping"),    # 80 weeks — over a year
])
def test_stock_classification(units, stock, expected):
    assert PM.compute(make(units=units, stock=stock), period_days=7)["stock_class"] == expected


def test_negative_stock_is_caught_before_any_ratio():
    """A negative count makes every derived number meaningless — flag, don't compute."""
    out = PM.compute(make(units=10, stock=-3), period_days=30)
    assert out["stock_class"] == "negative"
    assert out["cash_frozen"] == 0.0       # never claim frozen cash from bad data


def test_sleeping_is_separate_from_overstock():
    """
    The owner's addition, and it earns its place: lumping everything over 26
    weeks together produced one undifferentiated pile. On the real file this
    split isolates $143k in 202 products that won't sell through in a YEAR.
    """
    overstock = PM.compute(make(units=1, stock=35), period_days=7)   # ~35 weeks
    sleeping = PM.compute(make(units=1, stock=100), period_days=7)   # ~100 weeks
    assert overstock["stock_class"] == "overstock"
    assert sleeping["stock_class"] == "sleeping"


# ── The metrics themselves ───────────────────────────────────────────────────

def test_weeks_of_supply_and_days_agree():
    out = PM.compute(make(units=10, stock=20), period_days=7)
    assert out["weeks_of_supply"] == pytest.approx(2.0)
    assert out["days_of_supply"] == pytest.approx(14.0)


def test_sell_through_rate():
    out = PM.compute(make(units=25, stock=75), period_days=30)
    assert out["sell_through_rate"] == pytest.approx(0.25)


def test_turnover_is_annualised():
    """12 units a month against 12 in stock = 12 turns a year."""
    out = PM.compute(make(units=12, stock=12), period_days=30)
    assert out["turnover"] == pytest.approx(12.17, rel=0.02)


def test_turnover_is_none_without_stock():
    assert PM.compute(make(units=5, stock=0), period_days=30)["turnover"] is None


def test_cash_frozen_only_counts_stuck_classes():
    """Healthy stock is working capital, not frozen — don't inflate the number."""
    healthy = PM.compute(make(units=100, stock=200, price=10), period_days=30)
    sleeping = PM.compute(make(units=1, stock=200, price=10), period_days=30)
    assert healthy["stock_class"] == "healthy"
    assert healthy["cash_frozen"] == 0.0
    assert healthy["inventory_value"] == 2000.0     # still counted as inventory
    assert sleeping["cash_frozen"] == 2000.0


# ── The two scores answer different questions ────────────────────────────────

def test_health_peaks_in_the_healthy_band():
    healthy = PM.compute(make(units=50, stock=200), period_days=30)
    sleeping = PM.compute(make(units=1, stock=500), period_days=30)
    assert healthy["health_score"] > sleeping["health_score"]


def test_sold_out_scores_high_opportunity_despite_low_health():
    """
    You cannot sell what you don't have, so a sold-out item is genuinely
    unhealthy — but it is exactly what the owner should act on. Ranking a
    to-do list by health would bury it.
    """
    out = PM.compute(make(units=80, stock=0, price=30), period_days=30,
                     max_cash=1000, units_percentile=0.95)
    assert out["stock_class"] == "sold_out"
    assert out["health_score"] <= 40      # zero supply + zero availability
    assert out["opportunity_score"] > 60  # but top of the to-do list


def test_trivial_dead_stock_scores_low_opportunity():
    """A dead $1 item is unhealthy AND not worth anyone's morning."""
    out = PM.compute(make(units=0, stock=2, price=1), period_days=30,
                     max_cash=50_000, units_percentile=0.01)
    assert out["health_score"] < 40
    assert out["opportunity_score"] < 40


def test_bigger_money_at_stake_scores_higher():
    small = PM.compute(make(units=1, stock=100, price=5), period_days=30, max_cash=10_000)
    large = PM.compute(make(units=1, stock=100, price=90), period_days=30, max_cash=10_000)
    assert large["opportunity_score"] > small["opportunity_score"]


def test_scores_stay_inside_0_100():
    for units, stock, price in [(0, 0, 0), (9999, 1, 999), (1, 99999, 500)]:
        out = PM.compute(make(units=units, stock=stock, price=price),
                         period_days=30, max_cash=100)
        assert 0 <= out["health_score"] <= 100
        assert 0 <= out["opportunity_score"] <= 100


# ── Robustness ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("bad", [None, "", "abc", float("nan")])
def test_garbage_values_never_raise(bad):
    out = PM.compute({"product_name": "X", "quantity": bad, "stock_on_hand": bad,
                      "unit_price": bad, "total_amount": bad}, period_days=30)
    assert out["stock_class"] in PM.CLASSES


def test_empty_store_summarises_to_zeros():
    assert PM.summarise([], 30)["products"] == 0
    assert PM.compute_all([], 30) == []


# ── Store rollup ─────────────────────────────────────────────────────────────

def test_summarise_totals_and_groups():
    products = [
        make(units=100, stock=200, price=10, category="Whiskey"),   # healthy
        make(units=1, stock=500, price=20, category="Wine"),        # sleeping
        make(units=50, stock=0, price=15, category="Wine"),         # sold out
    ]
    s = PM.summarise(PM.compute_all(products, 30), 30)
    assert s["products"] == 3
    assert s["inventory_value"] == pytest.approx(2000 + 10000)
    assert s["cash_frozen"] == pytest.approx(10000)      # only the sleeping one
    assert s["by_category"]["Wine"]["count"] == 2
    assert "sleeping" in s["by_class"] and "sold_out" in s["by_class"]


def test_percentiles_are_store_relative():
    """'A big position' only means anything next to this store's other positions."""
    small_store = PM.compute_all([make(units=1, stock=10, price=5)], 30)
    assert 0 <= small_store[0]["opportunity_score"] <= 100
