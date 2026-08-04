"""
tests/test_bi_valuation.py — retail value is not cash.

The dashboard showed:

    Cash frozen   $220,661   70.4% of inventory

computed from unit_price, which is derived from sales as total ÷ quantity —
the SHELF price. The owner never spent $220,661; at a 30% margin he spent about
$154,000. The arithmetic was right and the label was wrong, which is worse than
an obvious error: it is the figure a shop owner checks first, and getting it
wrong costs trust in every other number on the page.

The rule under test: never assume a margin. Without one, report retail and say
"retail".
"""

import pytest

from app.services.bi import valuation as V

SUMMARY = {"inventory_value": 313347.0, "cash_frozen": 220661.0}


# ── Never invent a margin ────────────────────────────────────────────────────

def test_without_a_margin_nothing_claims_to_be_cash():
    out = V.build(SUMMARY, None)
    assert out["basis"] == "retail"
    assert out["inventory_cost"] is None and out["frozen_cost"] is None
    assert "retail" in out["frozen_label"].lower()
    assert out["frozen_label"] != "Cash frozen"


def test_the_retail_note_explains_why_there_is_no_cost_figure():
    note = V.build(SUMMARY, None)["note"].lower()
    assert "no cost data" in note
    assert "retail" in note


def test_the_headline_falls_back_to_retail():
    out = V.build(SUMMARY, None)
    assert out["frozen_headline"] == 220661.0


# ── With a margin, report cash ───────────────────────────────────────────────

def test_a_supplied_margin_produces_the_real_cash_figure():
    out = V.build(SUMMARY, 30)
    assert out["basis"] == "cost"
    assert out["frozen_cost"] == pytest.approx(154462.7)
    assert out["frozen_label"] == "Cash frozen"
    assert out["frozen_headline"] == out["frozen_cost"]


def test_retail_is_still_reported_alongside_cost():
    """Both are true and the owner may want either — never discard the retail."""
    out = V.build(SUMMARY, 30)
    assert out["inventory_retail"] == 313347.0
    assert out["frozen_retail"] == 220661.0


@pytest.mark.parametrize("margin,expected", [
    (25, 165495.75), (30, 154462.70), (35, 143429.65),
])
def test_cost_scales_with_margin(margin, expected):
    assert V.at_cost(220661.0, margin) == pytest.approx(expected)


def test_the_note_attributes_the_estimate_to_the_owners_own_number():
    assert "30%" in V.build(SUMMARY, 30)["note"]


# ── Rejecting nonsense ───────────────────────────────────────────────────────

@pytest.mark.parametrize("junk", [None, "", "abc", -5, 0, 99, 1000, float("nan")])
def test_implausible_margins_are_refused(junk):
    """A refused margin means retail-only, never a silently wrong cost."""
    assert V.normalise_margin(junk) is None
    assert V.build(SUMMARY, junk)["basis"] == "retail"


def test_zero_is_refused_because_nobody_sells_at_cost():
    """Taken literally, 0% would assert that cost equals retail."""
    assert V.normalise_margin(0) is None


@pytest.mark.parametrize("value,expected", [(1, 1), (30, 30), (90, 90), ("30", 30), (29.6, 30)])
def test_sane_margins_are_accepted(value, expected):
    assert V.normalise_margin(value) == expected


def test_at_cost_without_a_margin_returns_none_not_zero():
    """Returning 0.0 would render as "$0 of cash frozen" — worse than nothing."""
    assert V.at_cost(220661.0, None) is None


def test_an_empty_store_does_not_divide_by_anything():
    out = V.build({}, 30)
    assert out["inventory_retail"] == 0.0
    assert out["frozen_cost"] == 0.0


# ── The label and the number can never drift apart ───────────────────────────

@pytest.mark.parametrize("margin", [None, 30])
def test_the_basis_flag_always_matches_the_headline(margin):
    out = V.build(SUMMARY, margin)
    if out["basis"] == "cost":
        assert out["frozen_headline"] == out["frozen_cost"]
        assert "retail" not in out["frozen_label"].lower()
    else:
        assert out["frozen_headline"] == out["frozen_retail"]
        assert "retail" in out["frozen_label"].lower()
