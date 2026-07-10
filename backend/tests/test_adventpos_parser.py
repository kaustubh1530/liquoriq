"""
tests/test_adventpos_parser.py — Parser tests against a synthetic replica of
the real AdvEntPOS "Sales By Item Summary Report" (Phase 13).

Run from backend/:  pytest -v
"""

from datetime import date
from pathlib import Path

import pytest

from app.services.parsers.adventpos_parser import AdvEntPOSParser

FIXTURE = Path(__file__).parent / "fixtures" / "adventpos_summary_sample.xls"


@pytest.fixture(scope="module")
def rows():
    return AdvEntPOSParser().parse(str(FIXTURE))


def test_product_count(rows):
    # 4 real products. Wrapped continuations, page headers/footers, the grand
    # Total row, AND the page-boundary reprint of TEST VODKA must all be
    # excluded — none becomes a row of its own.
    assert len(rows) == 4


def test_page_boundary_reprint_deduplicated(rows):
    vodkas = [r for r in rows if "VODKA" in r["product_name"]]
    assert len(vodkas) == 1


def test_total_row_not_a_product(rows):
    assert not any(r["sku"] == "Total" for r in rows)


def test_wrapped_names_are_merged(rows):
    names = [r["product_name"] for r in rows]
    assert "TEST WHISKEY SINGLE BARREL RESERVE , 750 ml" in names
    assert "TEST WINE CABERNET SAUVIGNON RESERVE , 750 ml, GIFT BOX" in names


def test_totals_and_derived_unit_price(rows):
    total = sum(r["total_amount"] for r in rows)
    assert total == pytest.approx(203.64)

    whiskey = next(r for r in rows if r["product_name"].startswith("TEST WHISKEY"))
    assert whiskey["quantity"] == 2
    assert whiskey["unit_price"] == pytest.approx(30.86)  # 61.72 / 2


def test_stock_on_hand_captured(rows):
    beer = next(r for r in rows if "BEER" in r["product_name"])
    assert beer["stock_on_hand"] == 24


def test_sale_date_is_period_end(rows):
    assert all(r["sale_date"] == date(2026, 6, 7) for r in rows)


def test_skus_preserved_as_strings(rows):
    # Leading zeros must survive (dtype=str) — UPCs are identifiers, not numbers
    assert rows[0]["sku"] == "00000000001"
