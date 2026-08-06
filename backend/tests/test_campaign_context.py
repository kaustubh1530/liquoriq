"""
tests/test_campaign_context.py — PHASE 23.6: one campaign, understood once.

The rule that matters most here is not "does inference work" but **does every
inference land on a value the backend will accept**. A campaign_type of
"Seasonal Promotion" reads beautifully and is rejected at generation time,
long after the owner stopped looking at the form. Silent, late, and confusing.

So the vocabulary tests come first.
"""

import asyncio
import types

import pytest

from app.services import campaign_context as CTX
from app.services.design_plan import AD_LAYOUTS, CAMPAIGN_TYPES

_LOOP = asyncio.new_event_loop()


def _run(coro):
    return _LOOP.run_until_complete(coro)


def strategy(**kw):
    base = {
        "id": "abc-123",
        "strategy_title": "Labor Day Beer Blowout",
        "occasion": "Labor Day Weekend",
        "strategy_type": "seasonal",
        "recommended_offer": "Buy any 2 cases, save $10 — Modelo 12pk at $14.99",
        "reason": "Last big summer weekend and beer stock is heavy.",
        "target_customer_segment": "Weekend party shoppers",
        "expected_impact": "Higher basket size across the holiday weekend",
        "products_to_promote": ["Modelo Especial 12PK", "Truly Variety 12PK"],
    }
    return types.SimpleNamespace(**{**base, **kw})


async def build(s):
    """No DB — facts and photos are optional enrichment and degrade to empty."""
    return await CTX.build(s, "store-1", None)


# ── The vocabulary rule ──────────────────────────────────────────────────────

@pytest.mark.parametrize("s", [
    strategy(),
    strategy(occasion="Christmas", strategy_title="Premium Gift Season"),
    strategy(occasion="", strategy_title="New Arrival: Uncle Nearest"),
    strategy(occasion="", strategy_title="Allocated single barrel release"),
    strategy(occasion="", strategy_title="Wine tasting evening"),
    strategy(occasion="", strategy_title="Clearance blowout"),
])
def test_every_inferred_value_is_one_the_backend_accepts(s):
    """
    The whole point. An inferred value outside these sets is rejected at
    generation, which the owner experiences as the button not working.
    """
    pre = _run(build(s))["prefill"]
    assert pre["campaign_type"] in CAMPAIGN_TYPES
    assert pre["layout"] in AD_LAYOUTS
    assert pre["image_format"] in {"square", "portrait", "landscape"}


# ── Inference quality ────────────────────────────────────────────────────────

@pytest.mark.parametrize("title,expected", [
    ("New arrival: Uncle Nearest 1856", "new_arrival"),
    ("Limited allocated single barrel", "limited_edition"),
    ("Premium gift season", "premium_collection"),
    ("Whiskey tasting spotlight", "product_spotlight"),
    ("Weekend beer promotion", "standard"),
])
def test_campaign_type_is_inferred_from_the_strategy(title, expected):
    pre = _run(build(strategy(strategy_title=title, occasion="")))["prefill"]
    assert pre["campaign_type"] == expected


def test_a_beer_promotion_gets_the_bottom_band_layout():
    """Volume promotions need the price loud along the bottom."""
    assert _run(build(strategy()))["prefill"]["layout"] == "band"


def test_premium_spirits_get_the_vertical_rail():
    pre = _run(build(strategy(strategy_title="Premium whiskey reserve",
                              occasion="")))["prefill"]
    assert pre["layout"] == "rail"


def test_a_flyer_is_portrait_and_a_web_banner_is_landscape():
    assert _run(build(strategy(strategy_title="In-store flyer",
                               occasion="")))["prefill"]["image_format"] == "portrait"
    assert _run(build(strategy(strategy_title="Facebook cover banner",
                               occasion="")))["prefill"]["image_format"] == "landscape"


def test_the_default_format_is_square_for_social():
    assert _run(build(strategy()))["prefill"]["image_format"] == "square"


# ── Look and feel ────────────────────────────────────────────────────────────

def test_the_occasion_drives_the_scene():
    pre = _run(build(strategy()))["prefill"]
    assert "barbecue" in pre["instructions"].lower()


def test_the_occasion_beats_the_category():
    """A Christmas whiskey ad should look like Christmas, not like every other
    whiskey ad."""
    pre = _run(build(strategy(occasion="Christmas",
                              strategy_title="Premium whiskey gifting")))["prefill"]
    assert "fireplace" in pre["instructions"].lower()


def test_an_unknown_occasion_leaves_the_scene_empty_rather_than_generic():
    """An invented scene is worse than none — it art-directs the ad wrongly."""
    pre = _run(build(strategy(occasion="Tuesday", strategy_title="Weekly deal",
                              products_to_promote=[])))["prefill"]
    assert pre["instructions"] == ""


# ── The offer ────────────────────────────────────────────────────────────────

def test_the_offer_comes_straight_from_the_strategy():
    pre = _run(build(strategy()))["prefill"]
    assert pre["offer"] == strategy().recommended_offer


def test_the_bare_price_is_extracted_for_the_price_slot():
    assert _run(build(strategy()))["prefill"]["price"] == "$14.99"


def test_an_offer_with_no_price_yields_no_price():
    pre = _run(build(strategy(recommended_offer="Buy one get one free")))["prefill"]
    assert pre["price"] == ""


# ── Details are only switched on when there is something to show ─────────────

def test_details_stay_off_without_confirmed_facts():
    """An empty product-details panel is worse than none."""
    pre = _run(build(strategy(strategy_title="Premium gift")))["prefill"]
    assert pre["show_details"] is False


def test_nothing_about_the_product_is_invented():
    pre = _run(build(strategy()))["prefill"]
    assert pre["facts"] == {}
    assert pre["category"] == ""
    assert pre["product_url"] == ""


# ── The summary the owner reads before generating ────────────────────────────

def test_the_summary_carries_the_whole_recommendation():
    summary = _run(build(strategy()))["summary"]
    for key in ("campaign", "goal", "occasion", "audience", "offer",
                "primary_product", "expected_outcome"):
        assert summary[key], key
    assert summary["primary_product"] == "Modelo Especial 12PK"


def test_every_inference_explains_itself():
    """
    The owner needs to know the form was filled from his strategy rather than
    guessed at — and what to change if it guessed wrong.
    """
    reasons = _run(build(strategy()))["reasons"]
    for key in ("campaign_type", "layout", "image_format", "instructions", "offer"):
        assert reasons[key], key


def test_a_strategy_with_no_products_does_not_crash():
    out = _run(build(strategy(products_to_promote=[])))
    assert out["summary"]["primary_product"] == ""
    assert out["prefill"]["campaign_type"] in CAMPAIGN_TYPES


def test_a_bare_strategy_still_produces_a_usable_context():
    bare = types.SimpleNamespace(id="x", strategy_title="", occasion="",
                                 strategy_type="", recommended_offer="",
                                 reason="", target_customer_segment="",
                                 expected_impact="", products_to_promote=None)
    out = _run(build(bare))
    assert out["prefill"]["campaign_type"] == "standard"
    assert out["prefill"]["layout"] in AD_LAYOUTS


@pytest.mark.parametrize("offer,expected", [
    ("Buy any 2 cases, save $10 — Modelo 12pk at $14.99", "$14.99"),
    ("Lamarca Prosecco for $21.99 this weekend", "$21.99"),
    ("Only $9.99 while stocks last", "$9.99"),
    ("Save $5 on every bottle", "$5"),
    ("Buy 2, get the third at $12.00", "$12.00"),
])
def test_the_selling_price_wins_over_the_saving(offer, expected):
    """
    The first dollar amount in an offer is usually the DISCOUNT. Taking it
    would advertise a twelve-pack for the value of its own saving — the Phase
    22 hero-price bug, in a new place.
    """
    assert CTX.extract_price(offer) == expected
