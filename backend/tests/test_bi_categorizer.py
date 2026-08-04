"""
tests/test_bi_categorizer.py — PHASE 22: Category Intelligence Layer

The POS export has no category column, so everything category-shaped in the
product depends on this cascade being right. These tests pin the tier ORDER
(who wins when two tiers disagree), the non-product exclusion, and the
extraction of size/pack that upsell and bundle detection rely on.
"""

import pytest

from app.services.bi import assumptions as A
from app.services.bi import categorizer as C


# ── Tier order: the whole point of a cascade ─────────────────────────────────

def test_manual_override_beats_everything():
    """The owner's correction is absolute — even against a known brand."""
    out = C.categorize("TITO'S HANDMADE VODKA, 750 ml", sku="123",
                       overrides={"123": {"category": "Whiskey"}})
    assert out["category"] == "Whiskey"
    assert out["source"] == "manual"
    assert out["confidence"] == "certain"


def test_cache_beats_dictionaries_but_not_override():
    out = C.categorize("SOMETHING ODD", sku="9", cache={"9": "Wine"})
    assert (out["category"], out["source"]) == ("Wine", "cache")

    out = C.categorize("SOMETHING ODD", sku="9",
                       overrides={"9": "Beer"}, cache={"9": "Wine"})
    assert (out["category"], out["source"]) == ("Beer", "manual")


def test_brand_beats_keyword_dictionary():
    """'JACK DANIEL' is a brand hit; without it the word 'WHISKEY' would fire."""
    out = C.categorize("JACK DANIEL'S TENNESSEE WHISKEY, 750 ml")
    assert out["category"] == "Whiskey"
    assert out["source"] == "brand"
    assert out["brand"]


def test_longest_brand_match_wins():
    """BUD LIGHT SELTZER must not be classified as Beer by 'BUD LIGHT'."""
    assert C.categorize("BUD LIGHT SELTZER MANGO 12PK")["category"] == "Seltzer/RTD"


def test_cache_is_keyed_by_sku_not_name():
    """Names get re-typed between exports; the UPC is the stable identity."""
    out = C.categorize("RENAMED PRODUCT", sku="555", cache={"555": "Rum"})
    assert out["category"] == "Rum"


def test_unresolved_falls_back_and_is_flagged_for_ai():
    out = C.categorize("ZZQQ UNKNOWN THING")
    assert out["category"] == "Other"
    assert out["source"] == "fallback"
    assert out["needs_ai"] is True


# ── Non-product exclusion (found on the real file) ───────────────────────────

@pytest.mark.parametrize("name", [
    "TAX ITEM", "NON-TAX ITEM", "TIP", "UBER TIP", "UBER DELIVERY",
    "CITY HIVE DELIVERY FEE", "CITY HIVE TIP", "DC BAG TAX",
    "CREDIT/DEBIT CARD TRAN FEE", "DELIVERY CHARGE",
])
def test_fees_and_tips_are_not_products(name):
    """
    REGRESSION: these sit in the sales export next to real bottles. Before this,
    'TAX ITEM' was being reported as a sold-out product to reorder, and $1,402
    of tips/fees counted as product revenue.
    """
    assert C.categorize(name)["category"] == C.NON_PRODUCT


def test_real_products_are_not_swept_up_as_non_product():
    for name in ["TITO'S HANDMADE VODKA", "CORONA EXTRA 12PK", "CAYMUS CAB SAUV"]:
        assert C.categorize(name)["category"] != C.NON_PRODUCT


# ── Category coverage on real-world naming ───────────────────────────────────

@pytest.mark.parametrize("name,expected", [
    ("BUFFALO TRACE, 750 ml", "Whiskey"),
    ("TITO'S HANDMADE VODKA , 1.75 Lt", "Vodka"),
    ("PATRON SILVER, 750 ml", "Tequila"),
    ("BACARDI SUPERIOR, 1 Lt", "Rum"),
    ("TANQUERAY LONDON DRY, 750 ml", "Gin"),
    ("HENNESSY VS, 750 ml", "Cognac/Brandy"),
    ("BAILEYS IRISH CREAM, 750 ml", "Liqueur"),
    ("CAYMUS NAPA CAB SAUV , 750 ml", "Wine"),
    ("VEUVE CLICQUOT BRUT, 750 ml", "Champagne"),
    ("CORONA EXTRA 12PK 12OZ", "Beer"),
    ("WHITE CLAW MANGO 12PK", "Seltzer/RTD"),
    ("JINRO GREEN GRAPE , 375 ml", "Sake/Soju"),
    ("PEPSI , 2 LT", "Non-alcoholic"),
    ("MARLBORO RED BOX", "Tobacco"),
])
def test_known_products_classify(name, expected):
    assert C.categorize(name)["category"] == expected


@pytest.mark.parametrize("name", [
    "NOBILO SAUV BLANC, 750 ml",      # the abbreviation, not "Sauvignon"
    "LA CREMA SONOMA CHARD , 750 ml",  # "CHARD" not "Chardonnay"
    "MURPHY GOODE P NOIR , 750 ml",    # "P NOIR"
    "90 CELLARS SANCERRE, 750 ml",     # region implies wine
    "RIDOLFI BRUNELLO DI MONTALCINO, 750 ml",
    "BROADBENT VINHO VERDE, 750 ml",
])
def test_shop_floor_wine_abbreviations_classify(name):
    """Staff abbreviate varietals on tags; the abbreviations are what we see."""
    assert C.categorize(name)["category"] == "Wine"


# ── Size / pack extraction (feeds upsell + bundling) ─────────────────────────

@pytest.mark.parametrize("name,ml,pack", [
    ("TITO'S VODKA, 750 ml", 750.0, None),
    ("BACARDI, 1.75 Lt", 1750.0, None),
    ("CORONA , 12 Oz, 12-PACK CANS", 354.88, 12),
    ("BUSCH 6PK 12OZ CANS, 12 Oz, 6-Pack", 354.88, 6),
])
def test_size_and_pack_extraction(name, ml, pack):
    out = C.extract_size(name)
    assert out["size_ml"] == pytest.approx(ml, rel=0.01)
    assert out["pack_count"] == pack


def test_total_ml_multiplies_by_the_pack():
    """A 12-pack of 12oz is 12x the volume — that's what makes value comparable."""
    out = C.extract_size("CORONA , 12 Oz, 12-PACK CANS")
    assert out["total_ml"] == pytest.approx(out["size_ml"] * 12, rel=0.01)


def test_missing_size_is_none_not_zero():
    out = C.extract_size("MYSTERY ITEM")
    assert out["size_ml"] is None and out["total_ml"] is None


# ── Robustness + reporting ───────────────────────────────────────────────────

@pytest.mark.parametrize("junk", ["", "   ", None])
def test_never_raises_on_empty_input(junk):
    assert C.categorize(junk or "")["category"] in C.CATEGORIES


def test_coverage_report_counts_tiers():
    rows = [{"product_name": "TITO'S VODKA", "sku": "1"},
            {"product_name": "ZZQQ UNKNOWN", "sku": "2"}]
    cov = C.coverage(C.categorize_many(rows))
    assert cov["total"] == 2
    assert cov["resolved"] == 1
    assert cov["needs_ai"] == 1


def test_ai_may_only_choose_from_the_fixed_list():
    """GPT classifies; it never invents a category. The list is the contract."""
    assert "Wine" in C.CATEGORIES and "Other" in C.CATEGORIES
    assert len(C.CATEGORIES) == len(set(C.CATEGORIES))


# ── Assumptions module ───────────────────────────────────────────────────────

def test_every_score_weight_set_sums_to_one():
    """A typo here would silently skew every score in the product.
    (approx, not ==: 0.4+0.3+0.2+0.1 is 0.9999999999999999 in binary float.)"""
    assert (A.OPP_WEIGHT_MONEY + A.OPP_WEIGHT_URGENCY
            + A.OPP_WEIGHT_DEMAND) == pytest.approx(1.0)
    assert (A.HEALTH_WEIGHT_SUPPLY + A.HEALTH_WEIGHT_SELLTHROUGH
            + A.HEALTH_WEIGHT_REVENUE
            + A.HEALTH_WEIGHT_AVAILABILITY) == pytest.approx(1.0)
    assert (A.BIZ_WEIGHT_TURNOVER + A.BIZ_WEIGHT_HEALTHY_CASH
            + A.BIZ_WEIGHT_SELLTHROUGH + A.BIZ_WEIGHT_AVAILABILITY
            + A.BIZ_WEIGHT_DATA_QUALITY) == pytest.approx(1.0)


def test_stock_thresholds_are_ordered():
    assert (A.CRITICAL_WEEKS < A.REORDER_WEEKS < A.HEALTHY_MAX_WEEKS
            < A.HEAVY_MAX_WEEKS < A.OVERSTOCK_MAX_WEEKS)


def test_margins_are_plausible_fractions():
    for cat, m in A.CATEGORY_MARGINS.items():
        assert 0.0 < m < 1.0, cat


def test_assumptions_are_disclosable():
    """Every assumed number must be showable to the owner, not hidden."""
    disclosure = A.as_disclosure()
    assert len(disclosure) >= 5
    assert all({"key", "label", "value"} <= set(d) for d in disclosure)
