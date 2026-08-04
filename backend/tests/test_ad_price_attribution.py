"""
tests/test_ad_price_attribution.py — the price on an ad must belong to the
bottle on the ad.

THE BUG THIS EXISTS TO PREVENT
------------------------------
A real Labor Day campaign produced:

    products_to_promote[0] = "Tito's Handmade Vodka 1.75L"
    recommended_offer      = "Buy any 2 of the selected spirits, get Lamarca
                              Prosecco for $14.99"

The renderer put those together and printed a Tito's 1.75L advertisement
reading "AT $14.99". Tito's 1.75L sells for $29.99. The hero came from the
product list, the price came from the offer sentence, and nothing checked that
the two referred to the same bottle.

An advertised price is a promise the shop has to honour at the till, so this is
not a cosmetic defect. The rule these tests enforce: if we cannot attribute the
price to the bottle being shown, we do not print it as a price.
"""

import pytest

from app.services import design_plan as dp

PROMOTED = [
    "Tito's Handmade Vodka 1.75L", "Skrewball Peanut Butter 1L",
    "Jameson Irish 750ml", "Espolon Reposado 750ml", "Austin Hope Cab Sauv 750ml",
    "Freakshow Cab Sauv 750ml", "Lamarca Prosecco 750ml",
]
THE_OFFER = "Buy any 2 of the selected spirits, get Lamarca Prosecco for $14.99"


def plan(hero, offer, products=PROMOTED, known=None):
    return dp.validate_design_plan(
        {"headline": "Labor Day Bash", "subheadline": ""},
        hero, offer, None, promoted_products=products, known_unit_price=known,
    )


# ── The exact failure ────────────────────────────────────────────────────────

def test_the_prosecco_price_is_never_printed_on_the_vodka():
    """The regression test. $14.99 must not appear beside Tito's."""
    out = plan("Tito's Handmade Vodka 1.75L", THE_OFFER)
    assert "14.99" not in out["offer_text"], \
        "advertised the Prosecco's price on a bottle that costs twice as much"
    assert out["offer_is_amount"] is False


def test_the_offer_names_the_prosecco_as_its_subject():
    assert dp.find_offer_subject(THE_OFFER, PROMOTED) == "Lamarca Prosecco 750ml"


def test_on_the_right_bottle_the_price_appears_with_its_condition():
    """
    Correct hero, but the deal still requires buying two spirits first — so the
    price shows WITH the condition attached, never as a bare "AT $14.99".
    Suppressing it entirely would leave a chopped sentence in the slot, which
    is what made these ads look broken in the first place.
    """
    out = plan("Lamarca Prosecco 750ml", THE_OFFER)
    assert out["offer_text"] == "BUY 2, GET $14.99"
    assert out["offer_is_amount"] is False


# ── Subject matching ─────────────────────────────────────────────────────────

def test_a_simple_single_product_offer_still_works():
    out = plan("Lamarca Prosecco 750ml", "Lamarca Prosecco 750ml for $21.99 this weekend")
    assert out["offer_text"] == "$21.99"


def test_sizes_and_units_do_not_have_to_match_word_for_word():
    """The sentence writes "Lamarca Prosecco"; the product is "…750ml"."""
    assert dp.find_offer_subject("get Lamarca Prosecco for $14.99",
                                 ["Lamarca Prosecco 750ml"]) == "Lamarca Prosecco 750ml"


def test_a_shared_word_alone_does_not_pick_a_product():
    """
    "Cab Sauv" appears in two different wines. Matching on one shared token
    would attribute a price to whichever happened to be listed first.
    """
    assert dp.find_offer_subject("20% off Cab Sauv", PROMOTED) is None


def test_no_subject_when_the_offer_names_nothing():
    assert dp.find_offer_subject("Everything 20% off this weekend", PROMOTED) is None


def test_a_storewide_offer_keeps_its_price_on_any_hero():
    """Nothing to mis-attribute: the deal genuinely applies to the hero."""
    out = plan("Tito's Handmade Vodka 1.75L", "All spirits 20% off")
    assert out["offer_text"] == "20% OFF"


# ── Conditional offers ───────────────────────────────────────────────────────

@pytest.mark.parametrize("offer", [
    "Buy any 2 spirits, get Lamarca Prosecco for $14.99",
    "Get a free mixer with the purchase of any 1.75L at $9.99",
    "When you buy 2, the second is $5.00",
])
def test_a_conditional_price_is_never_typeset_as_a_flat_price(offer):
    """
    "AT $9.99" beside one bottle states an unconditional price. If the customer
    must buy something else to get it, printing it bare is misleading even when
    the product is right — so the renderer never gets the "amount" flag.
    """
    out = plan("Tito's Handmade Vodka 1.75L", offer, products=[])
    assert out["offer_is_amount"] is False
    assert out["offer_text"]  # but something readable is still shown


def test_bogo_survives_because_it_is_not_a_flat_price():
    """"BUY 2 GET 1 FREE" states its own condition — it isn't a bare amount."""
    out = plan("Tito's Handmade Vodka 1.75L", "Buy 2 get 1 free", products=[])
    assert "BUY 2 GET 1" in out["offer_text"].upper()


# ── The POS cross-check ──────────────────────────────────────────────────────

def test_a_price_far_below_the_shelf_price_is_rejected():
    """$14.99 against a $29.99 bottle is a different product, not a promotion."""
    assert dp.price_is_plausible("$14.99", 29.99) is False


@pytest.mark.parametrize("advertised,shelf", [
    ("$24.99", 29.99),   # a normal discount
    ("$19.99", 29.99),   # an aggressive discount
    ("$29.99", 29.99),   # no discount
    ("$59.98", 29.99),   # a two-bottle total
])
def test_genuine_promotions_are_not_blocked(advertised, shelf):
    """This guard catches wrong products, not keen pricing."""
    assert dp.price_is_plausible(advertised, shelf) is True


def test_no_reference_price_means_no_opinion():
    """Most stores won't have a clean price for every SKU. Don't block the ad."""
    assert dp.price_is_plausible("$14.99", None) is True
    assert dp.price_is_plausible("$14.99", 0) is True


def test_the_pos_check_is_wired_into_validation():
    out = plan("Tito's Handmade Vodka 1.75L",
               "Tito's Handmade Vodka 1.75L for $14.99", products=[], known=29.99)
    assert out["offer_text"] != "$14.99"


def test_a_plausible_price_survives_validation():
    out = plan("Tito's Handmade Vodka 1.75L",
               "Tito's Handmade Vodka 1.75L for $24.99", products=[], known=29.99)
    assert out["offer_text"] == "$24.99"


# ── Never break the existing contract ────────────────────────────────────────

def test_internal_numbers_are_still_scrubbed():
    out = plan("Lamarca Prosecco 750ml",
               "Lamarca Prosecco 750ml for $21.99 (46% margin)")
    assert "margin" not in out["offer_text"].lower()
    assert "46" not in out["offer_text"]


def test_an_empty_offer_does_not_crash():
    assert plan("Anything", "")["offer_text"] == ""
