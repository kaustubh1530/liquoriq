"""
tests/test_bi_reorder.py — PHASE 22: the reorder list

This list is the closest the product comes to spending the owner's money for
him, so the tests are about restraint as much as correctness:

  · never order what is already on the shelf
  · never order for a product that isn't selling
  · never present a retail figure as though it were cost
"""

import pytest

from app.services.bi import assumptions as A
from app.services.bi import reorder as R


def product(**kw):
    base = {
        "product_name": "Titos Handmade Vodka 750ml", "sku": "082000766",
        "category": "Vodka", "stock_class": "reorder", "units_sold": 40.0,
        "stock": 5.0, "weekly_velocity": 10.0, "weeks_of_supply": 0.5,
        "unit_price": 20.0,
    }
    return {**base, **kw}


# ── Never buy what you already have ──────────────────────────────────────────

def test_quantity_is_net_of_stock_on_hand():
    """10/week over 4 weeks = 40 needed, 15 on hand → order 25, not 40."""
    assert R.suggested_quantity(10.0, 15.0, 4.0) == 25


def test_a_product_with_enough_stock_is_not_ordered():
    assert R.suggested_quantity(10.0, 50.0, 4.0) == 0


def test_rows_with_nothing_to_order_are_dropped_entirely():
    rows = R.build_reorder_list([product(stock=100.0, weekly_velocity=1.0)])
    assert rows == []


def test_quantity_rounds_up():
    """3.2 bottles short means 4 — distributors don't split cases mid-bottle."""
    assert R.suggested_quantity(0.8, 0.0, 4.0) == 4


def test_negative_stock_is_treated_as_zero_not_as_credit():
    """
    A miscounted shelf shows -3. Subtracting a negative would ADD three
    bottles to the order — a data-entry error turning into a purchase.
    """
    assert R.suggested_quantity(10.0, -3.0, 4.0) == 40


# ── Only genuinely short, genuinely selling products ─────────────────────────

@pytest.mark.parametrize("stock_class", ["sold_out", "critical", "reorder"])
def test_short_classes_are_included(stock_class):
    rows = R.build_reorder_list([product(stock_class=stock_class, stock=0.0)])
    assert len(rows) == 1


@pytest.mark.parametrize("stock_class",
                         ["healthy", "heavy", "overstock", "sleeping", "dead", "negative"])
def test_other_classes_are_never_reordered(stock_class):
    assert R.build_reorder_list([product(stock_class=stock_class, stock=0.0)]) == []


def test_a_product_that_did_not_sell_is_never_reordered():
    """Zero sales means no demand signal. Buying more would be guessing."""
    assert R.build_reorder_list([product(units_sold=0.0, weekly_velocity=0.0)]) == []


# ── Ordering: urgency first, then value ──────────────────────────────────────

def test_out_of_stock_outranks_a_larger_low_stock_order():
    rows = R.build_reorder_list([
        product(product_name="Low stock, big money", stock_class="reorder",
                stock=5.0, weekly_velocity=50.0, unit_price=60.0),
        product(product_name="Out of stock, small", stock_class="sold_out",
                stock=0.0, weekly_velocity=1.0, unit_price=8.0),
    ])
    assert rows[0]["product_name"] == "Out of stock, small"
    assert rows[0]["urgency"] == "Out of stock"


def test_within_one_urgency_band_the_biggest_order_comes_first():
    rows = R.build_reorder_list([
        product(product_name="Small", unit_price=5.0),
        product(product_name="Large", unit_price=80.0),
    ])
    assert [r["product_name"] for r in rows] == ["Large", "Small"]


# ── The money column must not claim to be cost ───────────────────────────────

def test_the_value_field_is_named_as_retail():
    row = R.build_reorder_list([product()])[0]
    assert "line_value_at_retail" in row
    assert not any("cost" in key for key in row), \
        "no field may imply cost — the POS export has no cost data"


def test_line_value_is_quantity_times_retail_price():
    row = R.build_reorder_list([product(stock=0.0, weekly_velocity=10.0, unit_price=20.0)])[0]
    assert row["suggested_quantity"] == 40
    assert row["line_value_at_retail"] == 800.0


def test_csv_columns_never_use_the_word_cost():
    labels = " ".join(label for _, label in R.CSV_COLUMNS).lower()
    assert "cost" not in labels
    assert "retail" in labels


# ── Totals and the horizon ───────────────────────────────────────────────────

def test_totals_add_up():
    rows = R.build_reorder_list([
        product(product_name="A", stock=0.0, weekly_velocity=10.0, unit_price=20.0),
        product(product_name="B", stock_class="sold_out", stock=0.0,
                weekly_velocity=1.0, unit_price=10.0),
    ])
    totals = R.summarise(rows)
    assert totals["products"] == 2
    assert totals["total_units"] == sum(r["suggested_quantity"] for r in rows)
    assert totals["total_value_at_retail"] == pytest.approx(
        sum(r["line_value_at_retail"] for r in rows))
    assert totals["out_of_stock"] == 1


def test_the_horizon_defaults_to_the_documented_assumption():
    rows = R.build_reorder_list([product(stock=0.0, weekly_velocity=1.0)])
    assert rows[0]["suggested_quantity"] == int(A.REORDER_HORIZON_WEEKS)


def test_a_longer_horizon_orders_proportionally_more():
    four = R.build_reorder_list([product(stock=0.0, weekly_velocity=10.0)], 4.0)
    eight = R.build_reorder_list([product(stock=0.0, weekly_velocity=10.0)], 8.0)
    assert eight[0]["suggested_quantity"] == 2 * four[0]["suggested_quantity"]


def test_an_empty_store_produces_an_empty_list_not_an_error():
    assert R.build_reorder_list([]) == []
    assert R.summarise([])["products"] == 0
