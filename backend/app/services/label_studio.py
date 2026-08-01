"""
services/label_studio.py — MODULE 2: LABEL STUDIO (templates + design rules)

RESPONSIBILITY: promotional labels and badges. Nothing else. This module knows
nothing about strategies, GPT, or image generation.

It owns:
  - LABEL_TEMPLATES: the professional starter set every owner gets
  - new_label(): turn a template key into a full label object
  - validate_design(): sanitize/clamp any design document coming from the browser

Templates live on the SERVER (not hard-coded in the frontend) so we can add a
seasonal badge without shipping a frontend deploy, and so the shapes/limits are
unit-testable.

Pure functions (no DB / no network) → fully unit-tested.
"""

import uuid

# ── Shapes the canvas knows how to draw ───────────────────────────────────────
SHAPES = [
    "rectangle", "rounded", "circle", "pill", "ribbon", "price_tag",
    "starburst", "burst", "seal", "banner", "speech_bubble", "none",
]

# ── Limits ────────────────────────────────────────────────────────────────────
MAX_LABELS = 40
MAX_TEXT = 60
MAX_SUBTEXT = 60
MIN_SIZE = 24
MAX_CANVAS = 4096

# Palette used by the starter templates — deliberately few, strong colours.
_RED = "#c1121f"
_INK = "#14213d"
_GOLD = "#e9a615"
_GREEN = "#2a9d8f"
_PLUM = "#5f0f40"
_CHARCOAL = "#1d1d1d"
_WHITE = "#ffffff"

# ── Starter templates ─────────────────────────────────────────────────────────
# Each is a ready-made, professionally proportioned badge the owner can drop on
# the ad and then edit freely.
LABEL_TEMPLATES: list[dict] = [
    # Price / value
    {"key": "only_price",     "group": "Price",  "text": "ONLY $19.99",         "shape": "price_tag",     "shapeFill": _RED,      "fill": _WHITE, "width": 300, "height": 110, "fontSize": 44},
    {"key": "save_amount",    "group": "Price",  "text": "SAVE $10",            "shape": "starburst",     "shapeFill": _RED,      "fill": _WHITE, "width": 220, "height": 220, "fontSize": 42},
    {"key": "buy2get1",       "group": "Price",  "text": "BUY 2 GET 1",         "shape": "ribbon",        "shapeFill": _INK,      "fill": _WHITE, "width": 320, "height": 88,  "fontSize": 36},
    {"key": "off_10",         "group": "Price",  "text": "10% OFF",             "shape": "circle",        "shapeFill": _RED,      "fill": _WHITE, "width": 180, "height": 180, "fontSize": 38},
    {"key": "off_15",         "group": "Price",  "text": "15% OFF",             "shape": "circle",        "shapeFill": _RED,      "fill": _WHITE, "width": 180, "height": 180, "fontSize": 38},
    {"key": "off_20",         "group": "Price",  "text": "20% OFF",             "shape": "circle",        "shapeFill": _RED,      "fill": _WHITE, "width": 180, "height": 180, "fontSize": 38},
    {"key": "clearance",      "group": "Price",  "text": "CLEARANCE",           "shape": "banner",        "shapeFill": _CHARCOAL, "fill": _GOLD,  "width": 320, "height": 84,  "fontSize": 36},
    {"key": "member_deal",    "group": "Price",  "text": "MEMBER DEAL",         "shape": "pill",          "shapeFill": _PLUM,     "fill": _WHITE, "width": 290, "height": 74,  "fontSize": 32},

    # Urgency
    {"key": "limited_time",   "group": "Urgency","text": "LIMITED TIME",        "shape": "banner",        "shapeFill": _RED,      "fill": _WHITE, "width": 320, "height": 80,  "fontSize": 34},
    {"key": "while_supplies", "group": "Urgency","text": "WHILE SUPPLIES LAST", "shape": "rounded",       "shapeFill": _CHARCOAL, "fill": _WHITE, "width": 360, "height": 68,  "fontSize": 26},
    {"key": "weekend_special","group": "Urgency","text": "WEEKEND SPECIAL",     "shape": "ribbon",        "shapeFill": _PLUM,     "fill": _WHITE, "width": 340, "height": 84,  "fontSize": 32},
    {"key": "in_stock",       "group": "Urgency","text": "IN STOCK",            "shape": "pill",          "shapeFill": _GREEN,    "fill": _WHITE, "width": 220, "height": 66,  "fontSize": 30},

    # Product status
    {"key": "new_arrival",    "group": "Product","text": "NEW ARRIVAL",         "shape": "pill",          "shapeFill": _INK,      "fill": _WHITE, "width": 280, "height": 72,  "fontSize": 32},
    {"key": "limited_edition","group": "Product","text": "LIMITED EDITION",     "shape": "seal",          "shapeFill": _GOLD,     "fill": _CHARCOAL, "width": 200, "height": 200, "fontSize": 28},
    {"key": "special_release","group": "Product","text": "SPECIAL RELEASE",     "shape": "banner",        "shapeFill": _INK,      "fill": _GOLD,  "width": 340, "height": 82,  "fontSize": 30},
    {"key": "top_shelf",      "group": "Product","text": "TOP SHELF",           "shape": "seal",          "shapeFill": _CHARCOAL, "fill": _GOLD,  "width": 190, "height": 190, "fontSize": 32},
    {"key": "bourbon_month",  "group": "Product","text": "BOURBON MONTH",       "shape": "ribbon",        "shapeFill": _GOLD,     "fill": _CHARCOAL, "width": 340, "height": 86, "fontSize": 30},

    # Social proof
    {"key": "staff_pick",     "group": "Praise", "text": "STAFF PICK",          "shape": "speech_bubble", "shapeFill": _GREEN,    "fill": _WHITE, "width": 260, "height": 110, "fontSize": 32},
    {"key": "best_seller",    "group": "Praise", "text": "BEST SELLER",         "shape": "starburst",     "shapeFill": _GOLD,     "fill": _CHARCOAL, "width": 210, "height": 210, "fontSize": 32},
    {"key": "customer_fav",   "group": "Praise", "text": "CUSTOMER FAVORITE",   "shape": "rounded",       "shapeFill": _PLUM,     "fill": _WHITE, "width": 360, "height": 72,  "fontSize": 28},
]

TEMPLATES_BY_KEY = {t["key"]: t for t in LABEL_TEMPLATES}

# Defaults applied to every label so the canvas never hits an undefined property.
LABEL_DEFAULTS: dict = {
    "kind": "badge",
    "text": "LABEL",
    "subtext": "",
    "shape": "rounded",
    "shapeFill": _RED,
    "fill": _WHITE,
    "fontFamily": "Arial",
    "fontStyle": "bold",
    "fontSize": 32,
    "align": "center",
    "x": 80.0,
    "y": 80.0,
    "width": 280.0,
    "height": 80.0,
    "rotation": 0.0,
    "opacity": 1.0,
    "cornerRadius": 14.0,
    "padding": 10.0,
    "strokeWidth": 0.0,
    "stroke": "#ffffff",
    "shadow": True,
    "locked": False,
    "visible": True,
}


def new_label(template_key: str | None = None, **overrides) -> dict:
    """Build a complete label object from a starter template (or from scratch)."""
    label = dict(LABEL_DEFAULTS)
    tpl = TEMPLATES_BY_KEY.get(template_key or "")
    if tpl:
        label.update({k: v for k, v in tpl.items() if k not in ("key", "group")})
        label["template"] = tpl["key"]
    label.update(overrides)
    label["id"] = overrides.get("id") or f"lbl-{uuid.uuid4().hex[:10]}"
    return _clean_label(label)


def _num(value, default: float, lo: float, hi: float) -> float:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return float(default)
    if n != n:  # NaN → would poison JSON and Konva alike
        return float(default)
    return float(min(max(n, lo), hi))


def _clean_label(raw: dict) -> dict:
    """Coerce one label to a safe, complete, canvas-renderable object."""
    out = dict(LABEL_DEFAULTS)
    out.update({k: v for k, v in raw.items() if k in LABEL_DEFAULTS or k in ("id", "template")})

    out["id"] = str(raw.get("id") or f"lbl-{uuid.uuid4().hex[:10]}")[:64]
    out["text"] = str(raw.get("text", LABEL_DEFAULTS["text"]))[:MAX_TEXT]
    out["subtext"] = str(raw.get("subtext") or "")[:MAX_SUBTEXT]
    out["shape"] = raw.get("shape") if raw.get("shape") in SHAPES else LABEL_DEFAULTS["shape"]

    out["x"] = _num(raw.get("x"), LABEL_DEFAULTS["x"], -MAX_CANVAS, MAX_CANVAS)
    out["y"] = _num(raw.get("y"), LABEL_DEFAULTS["y"], -MAX_CANVAS, MAX_CANVAS)
    out["width"] = _num(raw.get("width"), LABEL_DEFAULTS["width"], MIN_SIZE, MAX_CANVAS)
    out["height"] = _num(raw.get("height"), LABEL_DEFAULTS["height"], MIN_SIZE, MAX_CANVAS)
    out["rotation"] = _num(raw.get("rotation"), 0.0, -360, 360)
    out["opacity"] = _num(raw.get("opacity"), 1.0, 0.0, 1.0)
    out["fontSize"] = _num(raw.get("fontSize"), LABEL_DEFAULTS["fontSize"], 8, 400)
    out["cornerRadius"] = _num(raw.get("cornerRadius"), LABEL_DEFAULTS["cornerRadius"], 0, 400)
    out["padding"] = _num(raw.get("padding"), LABEL_DEFAULTS["padding"], 0, 200)
    out["strokeWidth"] = _num(raw.get("strokeWidth"), 0.0, 0, 40)

    out["locked"] = bool(raw.get("locked", False))
    out["visible"] = bool(raw.get("visible", True))
    out["shadow"] = bool(raw.get("shadow", True))
    return out


def validate_design(design: dict | None, base_image_url: str = "", canvas: dict | None = None) -> dict:
    """
    Sanitize a design document from the browser. Never raises — a malformed or
    hostile payload degrades to an empty, valid design rather than a 500.

    Guarantees: canvas is sane, base_image is a string, labels is a list of
    complete label objects with unique ids, capped at MAX_LABELS.
    """
    design = design if isinstance(design, dict) else {}
    raw_canvas = design.get("canvas") if isinstance(design.get("canvas"), dict) else (canvas or {})

    width = int(_num((raw_canvas or {}).get("width"), 1024, 64, MAX_CANVAS))
    height = int(_num((raw_canvas or {}).get("height"), 1024, 64, MAX_CANVAS))

    raw_labels = design.get("labels")
    labels: list[dict] = []
    seen_ids: set[str] = set()
    if isinstance(raw_labels, list):
        for raw in raw_labels[:MAX_LABELS]:
            if not isinstance(raw, dict):
                continue
            label = _clean_label(raw)
            while label["id"] in seen_ids:            # ids must be unique (React keys)
                label["id"] = f"lbl-{uuid.uuid4().hex[:10]}"
            seen_ids.add(label["id"])
            labels.append(label)

    return {
        "canvas": {"width": width, "height": height},
        "base_image": str(design.get("base_image") or base_image_url or ""),
        "labels": labels,
    }


def empty_design(base_image_url: str, width: int = 1024, height: int = 1024) -> dict:
    """A fresh design: the untouched base image and no labels yet."""
    return validate_design(
        {"canvas": {"width": width, "height": height}, "base_image": base_image_url, "labels": []},
        base_image_url,
    )
