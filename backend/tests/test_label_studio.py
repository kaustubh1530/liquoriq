"""
tests/test_label_studio.py — MODULE 2: LABEL STUDIO (shelf labels)

The browser is untrusted, and a shelf label goes on a physical shelf where a
wrong price is a real problem. So: validation never raises, always produces a
renderable label, and the price the owner typed is the price that renders.
"""

from io import BytesIO

import pytest
from PIL import Image

from app.services import shelf_label as sl
from app.services import shelf_label_renderer as slr


# ── Catalogue ─────────────────────────────────────────────────────────────────

def test_sizes_are_sane_print_dimensions():
    for key, spec in sl.LABEL_SIZES.items():
        w, h = spec["inches"]
        assert 1.0 <= w <= 12 and 1.0 <= h <= 12, key
        px_w, px_h = sl.size_pixels(key)
        assert px_w == int(w * sl.DPI) and px_h == int(h * sl.DPI)


def test_themes_have_every_colour_the_renderer_reads():
    for key, theme in sl.THEMES.items():
        for field in ("bg", "ink", "muted", "accent", "accent_ink", "border"):
            assert theme[field].startswith("#") and len(theme[field]) == 7, f"{key}.{field}"


def test_renderer_and_catalogue_agree_on_icons():
    """A UI offering an icon the renderer can't draw would silently render nothing."""
    assert slr.DRAWABLE_ICONS <= set(sl.ICONS)


def test_unknown_size_theme_icon_fall_back():
    label = sl.validate_label({"size": "billboard", "theme": "neon", "icon": "spaceship"})
    assert label["size"] == sl.DEFAULT_SIZE
    assert label["theme"] == sl.DEFAULT_THEME
    assert label["icon"] == sl.DEFAULT_ICON


# ── Validation: never raise, always renderable ────────────────────────────────

@pytest.mark.parametrize("junk", [None, {}, {"details": "nope"}, {"rating": 7},
                                  {"details": [None, 3]}, {"product_name": None}])
def test_validate_never_raises(junk):
    label = sl.validate_label(junk)
    assert isinstance(label["details"], list)
    assert label["rating"]["kind"] in sl.RATING_KINDS


def test_price_is_preserved_exactly():
    """The whole point: what the owner typed is what goes on the shelf."""
    for price in ["$27.99", "2 for $30", "$8", "£12.50"]:
        assert sl.validate_label({"price": price})["price"] == price


def test_long_fields_are_truncated_not_dropped():
    label = sl.validate_label({"product_name": "A" * 500, "tagline": "B" * 200})
    assert len(label["product_name"]) == sl.NAME_MAX
    assert len(label["tagline"]) == sl.TAGLINE_MAX


def test_tagline_is_uppercased():
    assert sl.validate_label({"tagline": "staff pick"})["tagline"] == "STAFF PICK"


def test_details_capped_and_deduped():
    label = sl.validate_label({"details": ["90 proof", "90 proof", "750 ML", "Oak", "Extra"]})
    assert len(label["details"]) <= sl.DETAILS_MAX_ITEMS
    assert len(label["details"]) == len(set(d.lower() for d in label["details"]))


# ── Ratings ───────────────────────────────────────────────────────────────────

def test_stars_snap_to_half_and_clamp():
    assert sl.validate_rating({"kind": "stars", "value": 4.3})["value"] == 4.5
    assert sl.validate_rating({"kind": "stars", "value": 99})["value"] == sl.STARS_MAX
    assert sl.validate_rating({"kind": "stars", "value": -5})["value"] == 0.0


def test_points_clamp_to_the_scale():
    assert sl.validate_rating({"kind": "points", "value": 500})["value"] == sl.POINTS_MAX
    assert sl.validate_rating({"kind": "points", "value": 3})["value"] == sl.POINTS_MIN


def test_rating_nan_is_rejected():
    assert sl.validate_rating({"kind": "stars", "value": float("nan")})["value"] == 0.0


def test_rating_none_zeroes_out():
    r = sl.validate_rating({"kind": "none", "value": 5, "source": "Vivino"})
    assert r == {"kind": "none", "value": 0.0, "source": ""}


def test_unknown_rating_kind_falls_back_to_none():
    assert sl.validate_rating({"kind": "emoji"})["kind"] == "none"


# ── Rendering ─────────────────────────────────────────────────────────────────

def _render(spec):
    return Image.open(BytesIO(slr._render(spec)))


def test_renders_every_theme_and_size():
    for theme in sl.THEMES:
        for size in sl.LABEL_SIZES:
            img = _render({"theme": theme, "size": size,
                           "product_name": "Test Bottle", "price": "$19.99"})
            assert img.size == sl.size_pixels(size)


def test_renders_when_everything_is_empty():
    """A blank label must still produce a valid image, not crash."""
    img = _render({})
    assert img.size == sl.size_pixels(sl.DEFAULT_SIZE)


def test_crowded_label_still_fits_the_card():
    """Long name + every optional block must not overflow — the compaction pass."""
    img = _render({
        "size": "small", "theme": "premium", "icon": "bottle",
        "product_name": "Woodford Reserve Distillers Select Kentucky Straight Bourbon",
        "price": "$39.99", "was_price": "$45.99", "tagline": "New Arrival",
        "details": ["90.4 proof", "Aged in oak", "750 ML"],
        "rating": {"kind": "stars", "value": 5, "source": "Vivino"},
    })
    w, h = sl.size_pixels("small")
    assert img.size == (w, h)
    # The bottom strip holds the price: it must not be blank (price rendered) …
    bottom = img.crop((0, int(h * 0.72), w, h)).convert("RGB")
    assert len(bottom.getcolors(maxcolors=100000)) > 1


def test_all_icons_draw_without_error():
    for icon in slr._ICON_FNS:
        img = _render({"icon": icon, "product_name": "X", "price": "$1.99"})
        assert img.size == sl.size_pixels(sl.DEFAULT_SIZE)


def test_stars_and_points_both_render():
    for rating in ({"kind": "stars", "value": 3.5}, {"kind": "points", "value": 92}):
        img = _render({"product_name": "X", "price": "$1.99", "rating": rating})
        assert img.size[0] > 0


# ── Print sheet ───────────────────────────────────────────────────────────────

def test_labels_per_page_is_positive_and_size_dependent():
    small = slr.labels_per_page("small")
    large = slr.labels_per_page("large")
    assert small > large >= 1


def test_sheet_paginates_and_is_a_pdf():
    specs = [{"product_name": f"Bottle {i}", "price": f"${i}.99", "size": "small"}
             for i in range(slr.labels_per_page("small") + 3)]
    pdf = slr._render_sheet(specs, "small")
    assert pdf[:4] == b"%PDF"           # really a PDF
    assert len(pdf) > 1000


def test_sheet_of_one_label_works():
    pdf = slr._render_sheet([{"product_name": "Solo", "price": "$9.99"}], "medium")
    assert pdf[:4] == b"%PDF"


# ── Summary helper ────────────────────────────────────────────────────────────

def test_label_summary_prefers_name_and_price():
    assert sl.label_summary({"product_name": "Tito's", "price": "$21.99"}) == "Tito's — $21.99"
    assert sl.label_summary({"product_name": "Tito's", "price": ""}) == "Tito's"
    assert sl.label_summary({}) == "Untitled label"
