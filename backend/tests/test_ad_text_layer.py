"""
tests/test_ad_text_layer.py — MODULE 1: AI AD CREATOR (deterministic text layer)

The layer that turns "the AI made a picture" into "we made an ad". What matters:
the price is exact, the headline is never silently shortened, the photo is still
visible, and each ad uses its own accent colour rather than one shared template.
"""

from io import BytesIO

import pytest
from PIL import Image

from app.services import ad_text_renderer as atr
from app.services import design_plan as dp


def _scene(w=1024, h=1024, color=(120, 90, 60)):
    buf = BytesIO()
    Image.new("RGB", (w, h), color).save(buf, format="PNG")
    return buf.getvalue()


SPEC = {
    "eyebrow": "LABOR DAY",
    "headline": "Fire Up The Long Weekend",
    "subheadline": "Hand-picked bourbon for the grill",
    "price": "$27.99",
    "store_name": "Corner Wine & Spirits",
    "details": ["90 proof", "750 ML"],
    "accent": "#c1121f",
}


# ── Layout selection ──────────────────────────────────────────────────────────

def test_auto_layout_follows_the_frame_shape():
    """Poster is the default look; only wide frames get the banner treatment."""
    assert atr.choose_layout("auto", 1024, 1536) == "poster"   # portrait
    assert atr.choose_layout("auto", 1024, 1024) == "poster"   # square social
    assert atr.choose_layout("auto", 1536, 1024) == "banner"   # wide banner
    assert atr.choose_layout(None, 1024, 1024) == "poster"


def test_explicit_layout_wins():
    for name in atr.LAYOUTS:
        assert atr.choose_layout(name, 1024, 1024) == name


def test_unknown_layout_falls_back_to_auto():
    assert atr.choose_layout("hologram", 1024, 1024) == "poster"


# ── Rendering ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("layout", atr.LAYOUTS)
def test_every_layout_renders_at_every_format(layout):
    for w, h in [(1024, 1024), (1024, 1536), (1536, 1024)]:
        out = atr._render(_scene(w, h), SPEC, layout)
        assert Image.open(BytesIO(out)).size == (w, h)


def test_renders_with_only_a_headline():
    """Minimal spec — no price, no details, no eyebrow — must not crash."""
    out = atr._render(_scene(), {"headline": "Just A Headline"}, "band")
    assert Image.open(BytesIO(out)).size == (1024, 1024)


def test_renders_with_an_empty_spec():
    out = atr._render(_scene(), {}, "band")
    assert Image.open(BytesIO(out)).size == (1024, 1024)


def test_the_photo_is_not_blanketed():
    """
    v1 covered half the frame with a dark scrim and the owner said the ads went
    'too basic'. The artwork must survive: sample the right side, where the
    product lives, well away from any type.
    """
    base_color = (150, 110, 70)
    for layout in ("band", "poster"):
        img = Image.open(BytesIO(atr._render(_scene(color=base_color), SPEC, layout)))
        r, _g, _b = img.convert("RGB").getpixel((900, 300))
        assert abs(r - base_color[0]) < 40, f"{layout} darkened the artwork too much"


def test_poster_headline_clears_the_top_edge():
    """The owner's complaint was a clipped headline. Row 0 must be untouched."""
    img = Image.open(BytesIO(atr._render(_scene(color=(20, 30, 28)), SPEC, "poster")))
    px = img.convert("RGB")
    top_row = [px.getpixel((x, 2)) for x in range(0, 1024, 16)]
    assert all(sum(c) < 300 for c in top_row), "type is touching the top edge"


def test_poster_uses_the_product_name_in_the_offer():
    spec = {**SPEC, "product": "Sarti Rosa"}
    with_product = atr._render(_scene(), spec, "poster")
    without = atr._render(_scene(), {**SPEC, "product": ""}, "poster")
    assert with_product != without


def test_brushstroke_is_deterministic():
    """Same ad regenerated → same painted mark, not a different random blob."""
    a = atr._render(_scene(), SPEC, "poster")
    b = atr._render(_scene(), SPEC, "poster")
    assert a == b


# ── The two things that must never go wrong ───────────────────────────────────

def test_headline_is_not_silently_truncated():
    """
    A dropped word changes the message. If the headline can't fit it shrinks;
    if it truly cannot fit, it must be VISIBLY marked with an ellipsis.
    """
    from PIL import ImageDraw
    d = ImageDraw.Draw(Image.new("RGB", (1024, 1024)))
    text = "FIRE UP THE LONG WEEKEND"
    _f, lines, _h = atr._fit_block(d, text, atr._BOLD, 620, 400, 84, max_lines=2)
    joined = " ".join(lines)
    assert joined.endswith("…") or "WEEKEND" in joined


def test_wrap_marks_dropped_words():
    from PIL import ImageDraw
    d = ImageDraw.Draw(Image.new("RGB", (1024, 1024)))
    from PIL import ImageFont
    font = ImageFont.truetype(atr._BOLD, 80)
    lines = atr._wrap(d, "ONE TWO THREE FOUR FIVE SIX SEVEN EIGHT", font, 300, 2)
    assert lines[-1].endswith("…")


def test_no_headline_line_overflows_its_column():
    """
    REGRESSION: _fit_block once checked only "were words dropped", so a single
    long word ("CELEBRATION") sailed through at full size and ran over the
    bottle. Every line must fit the width budget.
    """
    from PIL import ImageDraw
    d = ImageDraw.Draw(Image.new("RGB", (1024, 1024)))
    budget = int(1024 * 0.56) / 0.88
    for text in ["CELEBRATION SIPS", "EXTRAORDINARILY LONG SINGLE WORD HEADLINE",
                 "SUPERCALIFRAGILISTICEXPIALIDOCIOUS"]:
        f, lines, _ = d and atr._fit_block(d, text, atr._BOLD, budget,
                                           int(1024 * 0.44), int(1024 * 0.115),
                                           max_lines=4, min_size=int(1024 * 0.05))
        for line in lines:
            assert d.textlength(line, font=f) <= budget + 1, f"{line!r} overflows"


# ── The price slot must hold a PRICE ──────────────────────────────────────────

@pytest.mark.parametrize("offer,expected", [
    ("Lamarca Prosecco 750ml for $21.99 this weekend", "$21.99"),
    ("20% off all Italian sparkling", "20% OFF"),
    ("BOGO free on select bourbon", "BOGO"),
    ("2 for $30 mix and match", "2 FOR $30"),
    ("Buy 2 get 1 free", "BUY 2 GET 1 FREE"),
])
def test_the_deal_is_extracted_from_the_offer_sentence(offer, expected):
    """
    REGRESSION: recommended_offer is a SENTENCE. Capping it to 24 chars put
    "Lamarca Prosecco 750ml…" in the price slot — the product name restated
    where the price should be.
    """
    assert dp.extract_price(offer) == expected


def test_offer_without_a_deal_falls_back_to_a_short_phrase():
    plan = dp.validate_design_plan({"headline": "X"}, "Gin", "Special weekend pricing")
    assert plan["offer_text"] == "Special weekend pricing"
    assert plan["offer_is_amount"] is False


def test_price_slot_never_holds_the_product_name():
    plan = dp.validate_design_plan(
        {"headline": "X"}, "Lamarca Prosecco 750ml",
        "Lamarca Prosecco 750ml for $21.99 this weekend")
    assert plan["offer_text"] == "$21.99"
    assert "lamarca" not in plan["offer_text"].lower()


def test_only_money_amounts_read_as_an_amount():
    """'AT $21.99' reads naturally; 'AT 20% OFF' does not."""
    assert dp.is_amount("$21.99") is True
    assert dp.is_amount("20% OFF") is False
    assert dp.is_amount("BOGO") is False


def test_price_string_reaches_the_renderer_untouched():
    """A bare price the owner typed is passed straight through."""
    plan = dp.validate_design_plan({"headline": "Sale"}, "Vodka", "$24.99")
    assert dp.ad_text_spec(plan, "My Store")["price"] == "$24.99"


# ── Accent colour ─────────────────────────────────────────────────────────────

def test_accent_hex_is_validated_and_expanded():
    assert dp._accent("#ABC") == "#aabbcc"
    assert dp._accent("#c1121f") == "#c1121f"


@pytest.mark.parametrize("bad", [None, "", "red", "#12", "javascript:alert(1)", 42, "#gggggg"])
def test_bad_accent_falls_back_instead_of_crashing_pillow(bad):
    assert dp._accent(bad) == dp.DEFAULT_ACCENT


def test_accent_flows_from_plan_into_the_spec():
    plan = dp.validate_design_plan(
        {"headline": "Hi", "accent_color": "#1f6feb"}, "Gin", "$19.99")
    assert dp.ad_text_spec(plan, "Store")["accent"] == "#1f6feb"


def test_different_accents_produce_different_pixels():
    """Proves the ad is coloured by its own plan, not a hard-coded template."""
    red = atr._render(_scene(), {**SPEC, "accent": "#c1121f"}, "band")
    blue = atr._render(_scene(), {**SPEC, "accent": "#1f6feb"}, "band")
    assert red != blue


def test_readable_ink_flips_on_light_accents():
    assert atr._readable_on((250, 230, 120)) == (17, 17, 17, 255)   # dark on gold
    assert atr._readable_on((30, 30, 60)) == atr.WHITE              # white on navy
