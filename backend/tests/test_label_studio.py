"""
tests/test_label_studio.py — MODULE 2: LABEL STUDIO (shelf labels)

A label is a list of positioned ELEMENTS. These go on a physical shelf where a
wrong price is a real problem, and the spec comes straight from the browser, so:
validation never raises, every element stays drawable, and the price the owner
typed is the price that prints.
"""

from io import BytesIO

import pytest
from PIL import Image

from app.services import shelf_label as sl
from app.services import shelf_label_renderer as slr


# ── Catalogue ─────────────────────────────────────────────────────────────────

def test_every_advertised_art_piece_is_drawable():
    """Art offered by the API but missing from the renderer would draw nothing."""
    assert set(slr._ART_FNS) == set(sl.ART)


def test_every_style_preset_builds_elements():
    for key in sl.STYLE_PRESETS:
        label = sl.build_from_style(key, {"product_name": "Test Bottle", "price": "$19.99",
                                          "regular_price": "$24.99", "subname": "Sub",
                                          "store_name": "Shop", "footer": "SALE"})
        assert label["elements"], key
        assert label["style"] == key


def test_sizes_are_sane_print_dimensions():
    for key, spec in sl.LABEL_SIZES.items():
        w, h = spec["inches"]
        assert 1.0 <= w <= 12 and 1.0 <= h <= 12, key
        assert sl.size_pixels(key) == (int(w * sl.DPI), int(h * sl.DPI))


def test_bundled_font_families_exist_on_disk():
    """The deploy container has no system fonts — every family must be bundled."""
    for family in sl.FONTS:
        bold, reg = slr._FAMILIES[family]
        assert bold.exists() and reg.exists(), family


def test_serif_is_the_default_house_style():
    assert sl.DEFAULT_FONT == "serif"
    assert sl.validate_label({})["font"] == "serif"


# ── Element validation ────────────────────────────────────────────────────────

@pytest.mark.parametrize("junk", [None, {}, {"elements": "nope"}, {"elements": [None, 5]},
                                  {"elements": [{}]}, {"size": "billboard"}])
def test_validate_never_raises(junk):
    label = sl.validate_label(junk)
    assert label["size"] in sl.LABEL_SIZES
    assert isinstance(label["elements"], list)


def test_element_positions_are_clamped():
    el = sl.validate_element({"x": 99, "y": -99, "w": 0, "size": 5, "rotation": 9999})
    assert -0.5 <= el["x"] <= 1.5
    assert -0.5 <= el["y"] <= 1.5
    assert el["w"] >= 0.03
    assert el["size"] <= 0.7
    assert -360 <= el["rotation"] <= 360


def test_nan_is_rejected():
    """NaN once poisoned our sales sums — never let it reach JSON or Pillow."""
    assert sl.validate_element({"x": float("nan")})["x"] == sl.ELEMENT_DEFAULTS["x"]


def test_unknown_kind_art_and_colour_fall_back():
    el = sl.validate_element({"kind": "hologram", "art": "spaceship", "color": "puce"})
    assert el["kind"] == "text"
    assert el["art"] in sl.ART
    assert el["color"] == "ink"


def test_custom_hex_colour_is_allowed():
    assert sl.validate_element({"color": "#ff8800"})["color"] == "#ff8800"


def test_duplicate_element_ids_are_made_unique():
    label = sl.validate_label({"elements": [{"id": "same", "text": "a"},
                                            {"id": "same", "text": "b"}]})
    ids = [e["id"] for e in label["elements"]]
    assert len(ids) == len(set(ids)) == 2


def test_element_count_is_capped():
    label = sl.validate_label({"elements": [{"text": str(i)} for i in range(200)]})
    assert len(label["elements"]) == sl.MAX_ELEMENTS


def test_text_is_truncated_not_dropped():
    assert len(sl.validate_element({"text": "A" * 500})["text"]) == sl.TEXT_MAX


# ── Money + the SAVE line the store writes by hand ────────────────────────────

@pytest.mark.parametrize("price,regular,expected", [
    ("$32.99", "$36.99", "SAVE $4 !"),
    ("29.99", "34.99", "SAVE $5 !"),
    ("$18.50", "$20.00", "SAVE $1.50 !"),
    ("$1,099", "$1,299", "SAVE $200 !"),
])
def test_savings_is_computed(price, regular, expected):
    assert sl.savings(price, regular) == expected


@pytest.mark.parametrize("price,regular", [
    ("$40", "$30"), ("$30", "$30"), ("$30", ""), ("", "$30"), ("call us", "$30"),
])
def test_no_savings_line_when_it_would_be_nonsense(price, regular):
    assert sl.savings(price, regular) == ""


def test_money_formatting_drops_pointless_cents():
    assert sl.fmt_money(4.0) == "$4"
    assert sl.fmt_money(4.5) == "$4.50"


def test_price_text_is_preserved_exactly():
    label = sl.build_from_style("classic", {"product_name": "X", "price": "2 for $30"})
    prices = [e["text"] for e in label["elements"] if e["kind"] == "price"]
    assert prices == ["2 for $30"]


def test_classic_preset_includes_the_computed_save_line():
    label = sl.build_from_style("classic", {"product_name": "W", "price": "$32.99",
                                            "regular_price": "$36.99"})
    assert any("SAVE $4 !" in e["text"] for e in label["elements"])


# ── Templates: save a look, reuse it ──────────────────────────────────────────

def test_template_keeps_the_layout_and_blanks_the_wording():
    source = sl.build_from_style("classic", {"product_name": "Woodford", "price": "$32.99",
                                             "regular_price": "$36.99"})
    tpl = sl.as_template(source, "Staff pick")
    assert len(tpl["elements"]) == len(source["elements"])       # layout intact
    assert all(e["text"] == "" for e in tpl["elements"]
               if e["kind"] in ("text", "price"))                # wording gone
    assert tpl["template_name"] == "Staff pick"


def test_applying_a_template_pours_wording_into_the_layout():
    tpl = sl.as_template(sl.build_from_style("classic",
        {"product_name": "Woodford", "price": "$32.99"}), "Look")
    content = sl.build_from_style("minimal", {"product_name": "Buffalo Trace", "price": "$27.99"})
    merged = sl.apply_template(tpl, content)
    texts = [e["text"] for e in merged["elements"] if e["text"]]
    assert "Buffalo Trace" in texts
    assert "$27.99" in texts


def test_template_name_defaults_when_blank():
    assert sl.as_template({}, "")["template_name"] == "Untitled style"


# ── Rendering ─────────────────────────────────────────────────────────────────

def _render(spec):
    return Image.open(BytesIO(slr._render(spec)))


def test_renders_every_style_size_and_font():
    for style in sl.STYLE_PRESETS:
        for size in sl.LABEL_SIZES:
            for font in sl.FONTS:
                label = sl.build_from_style(style, {"product_name": "Test Bottle",
                                                    "price": "$19.99"},
                                            {"size": size, "font": font})
                assert _render(label).size == sl.size_pixels(size)


def test_renders_a_completely_empty_label():
    assert _render({}).size == sl.size_pixels(sl.DEFAULT_SIZE)


def test_labels_are_printed_on_white():
    """Black on white is the house style — the paper must stay paper."""
    img = _render({"show_border": False, "elements": []})
    assert img.convert("RGB").getpixel((img.width // 2, 4)) == (255, 255, 255)


def test_all_art_pieces_draw():
    for art in sl.ART:
        label = {"elements": [{"kind": "art", "art": art, "x": 0.2, "y": 0.2, "w": 0.3}]}
        assert _render(label).size[0] > 0


def test_many_art_pieces_on_one_label():
    """The owner asked for multiple corner art — nothing caps art elements."""
    label = {"elements": [{"kind": "art", "art": a, "x": 0.05 + i * 0.08, "y": 0.6, "w": 0.07}
                          for i, a in enumerate(sl.ART)]}
    img = _render(label)
    assert img.size == sl.size_pixels(sl.DEFAULT_SIZE)


def test_a_broken_element_does_not_kill_the_label():
    """One bad element must degrade, not 500 the whole preview."""
    label = {"elements": [{"kind": "text", "text": "Fine", "x": 0.1, "y": 0.1},
                          {"kind": "art", "art": "bottles", "w": 0.0001}]}
    assert _render(label).size[0] > 0


def test_rotation_renders():
    label = {"elements": [{"kind": "text", "text": "Angled", "rotation": 25,
                           "x": 0.2, "y": 0.3, "w": 0.5}]}
    assert _render(label).size[0] > 0


# ── The boxes that drive the drag handles ─────────────────────────────────────

def test_preview_reports_a_box_per_visible_element():
    label = sl.build_from_style("classic", {"product_name": "Woodford", "price": "$32.99",
                                            "regular_price": "$36.99"})
    _png, boxes, (w, h) = slr._render(label, 0.4, True)
    visible = [e for e in label["elements"] if e["visible"]]
    assert len(boxes) == len(visible)
    assert w > 0 and h > 0


def test_boxes_are_relative_and_match_element_positions():
    """Handles are placed from these, so they must be in 0..1 card units."""
    label = {"elements": [{"id": "a", "kind": "text", "text": "Hi",
                           "x": 0.25, "y": 0.40, "w": 0.5, "size": 0.1}]}
    _png, boxes, _size = slr._render(label, 0.5, True)
    box = boxes[0]
    assert box["id"] == "a"
    assert abs(box["x"] - 0.25) < 0.01
    assert abs(box["y"] - 0.40) < 0.01
    assert abs(box["w"] - 0.5) < 0.01
    assert 0 < box["h"] < 1


def test_hidden_elements_get_no_box():
    label = {"elements": [{"id": "a", "kind": "text", "text": "Hi", "visible": False}]}
    _png, boxes, _ = slr._render(label, 0.5, True)
    assert boxes == []


# ── Print sheets: N labels per A4/Letter page ─────────────────────────────────

def test_every_offered_layout_has_a_grid():
    for per_page, (cols, rows) in sl.SHEET_LAYOUTS.items():
        assert cols * rows == per_page, per_page


@pytest.mark.parametrize("per_page", [2, 4, 6, 9, 12])
def test_sheet_renders_for_each_per_page_count(per_page):
    label = sl.build_from_style("classic", {"product_name": "Bottle", "price": "$9.99"})
    pdf = slr._render_sheet([label], per_page, "a4", repeat=True)
    assert pdf[:4] == b"%PDF" and len(pdf) > 1000


def test_cell_size_shrinks_as_more_labels_fit():
    """12-up cells must be smaller than 2-up cells, or the maths is wrong."""
    big = sl.cell_inches(2, "a4")
    small = sl.cell_inches(12, "a4")
    assert small[0] < big[0] and small[1] < big[1]


def test_cells_fit_inside_the_page():
    for per_page in sl.SHEET_LAYOUTS:
        for page in sl.PAGE_SIZES:
            for orient in sl.ORIENTATIONS:
                cols, rows = sl.sheet_grid(per_page, orient)
                cw, ch = sl.cell_inches(per_page, page, orient)
                pw, ph = sl.page_inches(page, orient)
                assert cw * cols <= pw and ch * rows <= ph, (per_page, page, orient)
                assert cw > 0.5 and ch > 0.5


def test_landscape_transposes_the_grid_and_the_cell():
    """
    The reason this exists: 9-up on portrait A4 gives TALL cells, which left a
    wide shelf tag floating in empty space. Landscape must give wide cells.
    """
    pw, ph = sl.cell_inches(9, "a4", "portrait")
    lw, lh = sl.cell_inches(9, "a4", "landscape")
    assert ph > pw, "portrait cells should be taller than wide"
    assert lw > lh, "landscape cells should be wider than tall"
    assert sl.sheet_grid(6, "portrait") == (2, 3)
    assert sl.sheet_grid(6, "landscape") == (3, 2)


def test_orientation_changes_the_rendered_page_shape():
    label = sl.build_from_style("minimal", {"product_name": "B", "price": "$9.99"})
    portrait = slr._build_pages([label], 9, "a4", True, False, "portrait")[0]
    landscape = slr._build_pages([label], 9, "a4", True, False, "landscape")[0]
    assert portrait.height > portrait.width
    assert landscape.width > landscape.height


def test_unknown_orientation_falls_back_to_portrait_geometry():
    """Anything that isn't 'landscape' is treated as portrait — never a crash."""
    assert sl.page_inches("a4", "sideways") == sl.page_inches("a4", "portrait")


def test_repeat_fills_exactly_one_page():
    """'Print 12 of this tag' → one page, not twelve pages of one label each."""
    label = sl.build_from_style("minimal", {"product_name": "B", "price": "$9.99"})
    pages = slr._build_pages([label], 12, "a4", repeat=True, cut_marks=True)
    assert len(pages) == 1


def test_without_repeat_it_paginates():
    label = sl.build_from_style("minimal", {"product_name": "B", "price": "$9.99"})
    pages = slr._build_pages([label] * 10, 4, "a4", repeat=False, cut_marks=True)
    assert len(pages) == 3            # 4 + 4 + 2


def test_a4_and_letter_pages_differ_in_size():
    a4 = slr._build_pages([{}], 4, "a4", False, False, "portrait")[0]
    letter = slr._build_pages([{}], 4, "letter", False, False, "portrait")[0]
    assert a4.size != letter.size
    assert a4.height > letter.height  # A4 is the taller sheet


def test_unknown_per_page_falls_back_instead_of_crashing():
    assert sl.sheet_grid(7) == sl.SHEET_LAYOUTS[sl.DEFAULT_PER_PAGE]
    assert sl.sheet_grid(0) == sl.SHEET_LAYOUTS[sl.DEFAULT_PER_PAGE]


def test_label_renders_at_an_arbitrary_cell_size():
    """The payoff of relative positions: any cell shape still lays out."""
    label = sl.build_from_style("classic", {"product_name": "Woodford", "price": "$32.99"})
    for size in [(300, 600), (900, 300), (500, 500)]:
        assert Image.open(BytesIO(slr._render(label, size_px=size))).size == size


def test_sheet_preview_is_a_png():
    label = sl.build_from_style("minimal", {"product_name": "B", "price": "$1.99"})
    png = slr._render_sheet_preview([label], 6, "a4", repeat=True)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_empty_selection_is_rejected():
    # Drive the coroutine one step instead of asyncio.run(): the guard raises
    # before the first await, and spinning up a loop here would close the one
    # other async tests in this suite rely on.
    coro = slr.render_sheet([], 4, "a4")
    with pytest.raises(ValueError):
        coro.send(None)


def test_label_summary_uses_the_first_text_and_price():
    label = sl.build_from_style("classic", {"product_name": "Tito\'s", "price": "$21.99"})
    assert sl.label_summary(label).startswith("Tito")
    assert "$21.99" in sl.label_summary(label)
