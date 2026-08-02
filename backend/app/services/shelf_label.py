"""
services/shelf_label.py — MODULE 2: LABEL STUDIO (shelf label definition)

A shelf label is a list of positioned ELEMENTS on a printable card. Text, the
price, clip-art and decorations are all elements, so the owner can move, resize,
recolour, duplicate or delete any of them — and add as many pieces of art as
they like.

WHY ELEMENTS AND NOT A FIXED TEMPLATE: the first version laid everything out for
you, which produced tidy labels but no freedom. Styles still exist — they are
PRESETS that generate a good starting set of elements — but nothing is locked
once the label is on screen.

Positions are RELATIVE (0..1 of the card's width/height), so a label designed at
4×3″ still looks right when switched to 5×7″ or printed at any DPI.

Pure functions (no DB / no network / no Pillow) → fully unit-tested.
"""

import uuid

# ── Print sizes (inches → pixels at 300 DPI) ──────────────────────────────────
DPI = 300

LABEL_SIZES: dict[str, dict] = {
    "small":  {"key": "small",  "label": "Small shelf tag", "inches": (3.5, 2.0), "note": "Business-card size"},
    "medium": {"key": "medium", "label": "Standard talker", "inches": (4.0, 3.0), "note": "The usual shelf talker"},
    "wide":   {"key": "wide",   "label": "Wide strip",      "inches": (5.0, 3.0), "note": "Long names fit better"},
    "large":  {"key": "large",  "label": "Large card",      "inches": (5.0, 7.0), "note": "Endcaps & displays"},
}
DEFAULT_SIZE = "medium"


def size_pixels(size_key: str) -> tuple[int, int]:
    spec = LABEL_SIZES.get(size_key) or LABEL_SIZES[DEFAULT_SIZE]
    w, h = spec["inches"]
    return int(w * DPI), int(h * DPI)


# ── Fonts (all bundled — the deploy container has no system fonts) ───────────
FONTS: dict[str, dict] = {
    "serif":     {"key": "serif",     "label": "Classic serif", "note": "Like the store's Canva labels"},
    "serif_alt": {"key": "serif_alt", "label": "Times serif",   "note": "Lighter, more formal"},
    "sans":      {"key": "sans",      "label": "Modern sans",   "note": "Cleaner, contemporary"},
}
DEFAULT_FONT = "serif"

# ── Accents ───────────────────────────────────────────────────────────────────
ACCENTS: dict[str, dict] = {
    "red":    {"key": "red",    "label": "Sale red", "hex": "#c8102e"},
    "black":  {"key": "black",  "label": "Black",    "hex": "#111111"},
    "green":  {"key": "green",  "label": "Green",    "hex": "#1b7f4f"},
    "blue":   {"key": "blue",   "label": "Navy",     "hex": "#1d3557"},
    "gold":   {"key": "gold",   "label": "Gold",     "hex": "#b8860b"},
    "purple": {"key": "purple", "label": "Plum",     "hex": "#6a1b4d"},
}
DEFAULT_ACCENT = "red"

# Colour slots an element can use. Keeping these symbolic (rather than raw hex)
# means changing the accent restyles the whole label at once.
COLORS = ("ink", "accent", "paper", "muted")

# ── Clip-art catalogue ────────────────────────────────────────────────────────
# Each is drawn with Pillow primitives (no emoji: the print fonts have no emoji
# glyphs, so they would come out as empty boxes on paper). `aspect` is width÷height.
ART: dict[str, dict] = {
    "bottles":   {"key": "bottles",   "label": "Bottles & glass", "aspect": 1.25},
    "bottle":    {"key": "bottle",    "label": "Single bottle",   "aspect": 0.42},
    "barrel":    {"key": "barrel",    "label": "Oak barrel",      "aspect": 0.95},
    "grapes":    {"key": "grapes",    "label": "Grapes",          "aspect": 0.85},
    "wineglass": {"key": "wineglass", "label": "Wine glass",      "aspect": 0.70},
    "martini":   {"key": "martini",   "label": "Cocktail",        "aspect": 0.90},
    "beer":      {"key": "beer",      "label": "Beer mug",        "aspect": 0.95},
    "star":      {"key": "star",      "label": "Star",            "aspect": 1.00},
    "laurel":    {"key": "laurel",    "label": "Laurel",          "aspect": 1.30},
    "flourish":  {"key": "flourish",  "label": "Flourish",        "aspect": 3.00},
    "snowflake": {"key": "snowflake", "label": "Snowflake",       "aspect": 1.00},
}

# ── Elements ──────────────────────────────────────────────────────────────────
ELEMENT_KINDS = ("text", "price", "art", "starburst", "banner", "line")
ALIGNS = ("left", "center", "right")

TEXT_MAX = 60

ELEMENT_DEFAULTS = {
    "kind": "text",
    "text": "Text",
    "art": "bottles",
    "x": 0.08, "y": 0.08, "w": 0.50,
    "size": 0.10,          # font size as a fraction of card HEIGHT
    "align": "left",
    "color": "ink",
    "bold": True,
    "italic": False,
    "rotation": 0.0,
    "lines": 2,            # max wrapped lines before shrinking
    "visible": True,
    "locked": False,
}


def _num(value, default, lo, hi):
    try:
        n = float(value)
    except (TypeError, ValueError):
        return float(default)
    if n != n:                       # NaN would poison JSON and Pillow alike
        return float(default)
    return float(min(max(n, lo), hi))


def _txt(value, limit=TEXT_MAX, default=""):
    if value is None:
        return default
    return str(value).strip()[:limit]


def new_id(prefix="el") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def validate_element(raw: dict | None) -> dict:
    """One element, coerced into something always drawable. Never raises."""
    raw = raw if isinstance(raw, dict) else {}
    out = dict(ELEMENT_DEFAULTS)

    out["id"] = _txt(raw.get("id"), 40) or new_id()
    out["kind"] = raw.get("kind") if raw.get("kind") in ELEMENT_KINDS else "text"
    out["text"] = _txt(raw.get("text"), TEXT_MAX, "")
    out["art"] = raw.get("art") if raw.get("art") in ART else "bottles"

    # Positions may sit slightly off-card (bleed) but not wander into space
    out["x"] = _num(raw.get("x"), ELEMENT_DEFAULTS["x"], -0.5, 1.5)
    out["y"] = _num(raw.get("y"), ELEMENT_DEFAULTS["y"], -0.5, 1.5)
    out["w"] = _num(raw.get("w"), ELEMENT_DEFAULTS["w"], 0.03, 1.5)
    out["size"] = _num(raw.get("size"), ELEMENT_DEFAULTS["size"], 0.01, 0.7)
    out["rotation"] = _num(raw.get("rotation"), 0.0, -180, 180)
    out["lines"] = int(_num(raw.get("lines"), 2, 1, 4))

    out["align"] = raw.get("align") if raw.get("align") in ALIGNS else "left"
    color = raw.get("color")
    out["color"] = color if (color in COLORS or _is_hex(color)) else "ink"

    out["bold"] = bool(raw.get("bold", True))
    out["italic"] = bool(raw.get("italic", False))
    out["visible"] = bool(raw.get("visible", True))
    out["locked"] = bool(raw.get("locked", False))
    return out


def _is_hex(value) -> bool:
    return (isinstance(value, str) and value.startswith("#")
            and len(value) in (4, 7)
            and all(c in "0123456789abcdefABCDEF" for c in value[1:]))


MAX_ELEMENTS = 30


def validate_label(raw: dict | None) -> dict:
    """
    A whole label. Never raises — a malformed payload degrades to a blank card
    rather than a 500, because this comes straight from the browser.
    """
    raw = raw if isinstance(raw, dict) else {}

    elements, seen = [], set()
    for item in (raw.get("elements") or [])[:MAX_ELEMENTS]:
        el = validate_element(item)
        while el["id"] in seen:                 # ids must be unique (React keys)
            el["id"] = new_id()
        seen.add(el["id"])
        elements.append(el)

    return {
        "size": raw.get("size") if raw.get("size") in LABEL_SIZES else DEFAULT_SIZE,
        "font": raw.get("font") if raw.get("font") in FONTS else DEFAULT_FONT,
        "accent": raw.get("accent") if raw.get("accent") in ACCENTS else DEFAULT_ACCENT,
        "show_border": bool(raw.get("show_border", True)),
        "style": _txt(raw.get("style"), 30, "custom"),
        "elements": elements,
    }


# ── Money helpers (the SAVE line the store writes by hand) ────────────────────

def _money(value):
    if value is None:
        return None
    raw = str(value).strip().replace("$", "").replace(",", "").strip()
    if not raw:
        return None
    try:
        amount = float(raw)
    except ValueError:
        return None
    return None if (amount != amount or amount < 0) else amount


def fmt_money(amount: float) -> str:
    """$4 not $4.00; $32.99 keeps its cents — matching how the store writes them."""
    if abs(amount - round(amount)) < 0.005:
        return f"${int(round(amount))}"
    return f"${amount:,.2f}"


def savings(price, regular) -> str:
    """"SAVE $4 !" computed from the two prices; "" when there's no real saving."""
    p, r = _money(price), _money(regular)
    if p is None or r is None or r <= p:
        return ""
    return f"SAVE {fmt_money(r - p)} !"


# ── Style presets ─────────────────────────────────────────────────────────────
# Each returns a good STARTING set of elements. Everything is movable afterwards.

def _el(kind, text, x, y, w, size, **over):
    el = {"kind": kind, "text": text, "x": x, "y": y, "w": w, "size": size}
    el.update(over)
    return validate_element(el)


def preset_classic(c: dict) -> list[dict]:
    """Their Woodford tag: name on top, starburst, huge price, REGULAR + SAVE."""
    out = [_el("text", c["product_name"], 0.06, 0.06, 0.66, 0.15, lines=2)]
    if c.get("size_text"):
        out.append(_el("text", c["size_text"], 0.74, 0.08, 0.20, 0.062,
                       align="right", bold=False))
    if c.get("show_badge", True):
        out.append(_el("starburst", c.get("badge_text") or "Sale",
                       0.05, 0.40, 0.20, 0.055, color="paper", align="center"))
    out.append(_el("price", c["price"], 0.28, 0.34, 0.66, 0.24,
                   color="accent" if c.get("red_price") else "ink"))
    if c.get("regular_price"):
        out.append(_el("text", f"REGULAR: {c['regular_price']}", 0.14, 0.62, 0.72,
                       0.065, align="center", bold=False))
    save = savings(c.get("price"), c.get("regular_price"))
    if save:
        out.append(_el("text", save, 0.14, 0.71, 0.72, 0.075, align="center"))
    out.append(_el("art", "", 0.06, 0.78, 0.15, 0.10, art="bottles"))
    out.append(_el("art", "", 0.80, 0.78, 0.14, 0.10, art="barrel"))
    return out


def preset_price_first(c: dict) -> list[dict]:
    """Their Traveller tag: big red price on top, name below, banner at the foot."""
    out = [_el("price", c["price"], 0.06, 0.04, 0.88, 0.22,
               align="center", color="accent")]
    if c.get("regular_price"):
        out.append(_el("text", f"Regular: {c['regular_price']}", 0.06, 0.27, 0.88,
                       0.058, align="center", bold=False))
    # Spacing here is deliberate: a two-line name occupies ~2 × size × 1.12, so
    # the subname must start below that or the two overlap.
    out.append(_el("text", c["product_name"], 0.06, 0.35, 0.88, 0.115,
                   align="center", lines=2))
    if c.get("subname"):
        out.append(_el("text", c["subname"], 0.08, 0.62, 0.84, 0.062,
                       align="center", lines=2))
    if c.get("size_text"):
        out.append(_el("text", c["size_text"], 0.76, 0.77, 0.18, 0.045,
                       align="right", bold=False))
    footer = c.get("footer") or savings(c.get("price"), c.get("regular_price"))
    if footer:
        out.append(_el("text", footer, 0.06, 0.85, 0.88, 0.068,
                       align="center", color="accent"))
    return out


def preset_deal_bookend(c: dict) -> list[dict]:
    """Their Monte Alto tag: DEAL columns down both edges, content centred."""
    out = [
        _el("banner", "DEAL", 0.0, 0.0, 0.085, 0.055, color="paper", align="center"),
        _el("banner", "DEAL", 0.915, 0.0, 0.085, 0.055, color="paper", align="center"),
        _el("text", c["product_name"], 0.14, 0.10, 0.72, 0.125, align="center", lines=3),
    ]
    if c.get("subname"):
        out.append(_el("text", c["subname"], 0.16, 0.40, 0.68, 0.052,
                       align="center", bold=False, color="muted"))
    out.append(_el("price", c["price"], 0.14, 0.48, 0.72, 0.20, align="center"))
    if c.get("store_name"):
        out.append(_el("text", c["store_name"], 0.14, 0.85, 0.72, 0.062,
                       align="center", bold=False))
    return out


def preset_minimal(c: dict) -> list[dict]:
    """A clean starting point when the owner wants to lay it out themselves."""
    out = [_el("text", c["product_name"], 0.07, 0.12, 0.86, 0.14, align="center", lines=2)]
    out.append(_el("price", c["price"], 0.07, 0.45, 0.86, 0.26, align="center"))
    return out


STYLE_PRESETS = {
    "classic":      {"key": "classic",      "label": "Classic sale", "note": "Name, starburst, big price, REGULAR + SAVE", "build": preset_classic},
    "price_first":  {"key": "price_first",  "label": "Price first",  "note": "Big price on top, name below, banner", "build": preset_price_first},
    "deal_bookend": {"key": "deal_bookend", "label": "DEAL bookend", "note": "Vertical DEAL columns down both edges", "build": preset_deal_bookend},
    "minimal":      {"key": "minimal",      "label": "Minimal",      "note": "Just name and price — lay it out yourself", "build": preset_minimal},
}
DEFAULT_STYLE = "classic"

# The fields the "quick fill" form collects before generating a preset
CONTENT_FIELDS = ("product_name", "subname", "size_text", "price",
                  "regular_price", "badge_text", "footer", "store_name")


def build_from_style(style: str, content: dict | None = None, base: dict | None = None) -> dict:
    """
    Generate a full label from a style preset plus the owner's content.
    This is the "start me off" path; everything is editable afterwards.
    """
    content = {k: _txt((content or {}).get(k), TEXT_MAX) for k in CONTENT_FIELDS}
    content.setdefault("badge_text", "")
    content["show_badge"] = bool((base or {}).get("show_badge", True))
    content["red_price"] = bool((base or {}).get("red_price", False))

    preset = STYLE_PRESETS.get(style) or STYLE_PRESETS[DEFAULT_STYLE]
    elements = [e for e in preset["build"](content) if e["text"] or e["kind"] == "art"]

    return validate_label({
        "size": (base or {}).get("size", DEFAULT_SIZE),
        "font": (base or {}).get("font", DEFAULT_FONT),
        "accent": (base or {}).get("accent", DEFAULT_ACCENT),
        "show_border": (base or {}).get("show_border", True),
        "style": preset["key"],
        "elements": elements,
    })


def blank_label() -> dict:
    return build_from_style(DEFAULT_STYLE, {"product_name": "Bottle name", "price": "$00.00"})


def label_summary(label: dict) -> str:
    """Best guess at a name for the saved-label list: first text, then the price."""
    els = label.get("elements") or []
    name = next((e.get("text") for e in els if e.get("kind") == "text" and e.get("text")), "")
    price = next((e.get("text") for e in els if e.get("kind") == "price" and e.get("text")), "")
    if name and price:
        return f"{name} — {price}"
    return name or price or "Untitled label"


# ── Templates: save a LOOK, reuse it for any bottle ───────────────────────────

def as_template(label: dict, name: str = "") -> dict:
    """
    Keep the layout and styling, blank the wording. The owner sets up "our staff
    pick look" once and drops any bottle into it afterwards.
    """
    clean = validate_label(label)
    for el in clean["elements"]:
        if el["kind"] in ("text", "price"):
            el["text"] = ""
    clean["template_name"] = _txt(name, 40) or "Untitled style"
    return clean


def apply_template(template: dict, label: dict) -> dict:
    """
    Pour this label's WORDING into that template's layout, matching elements up
    in order per kind so the name lands in the name slot and the price in the
    price slot.
    """
    look = validate_label(template)
    content = validate_label(label)

    pools: dict[str, list[str]] = {}
    for el in content["elements"]:
        if el["kind"] in ("text", "price", "starburst", "banner") and el["text"]:
            pools.setdefault(el["kind"], []).append(el["text"])

    used: dict[str, int] = {}
    for el in look["elements"]:
        kind = el["kind"]
        if kind not in pools:
            continue
        i = used.get(kind, 0)
        if i < len(pools[kind]):
            el["text"] = pools[kind][i]
            used[kind] = i + 1
    return validate_label(look)
