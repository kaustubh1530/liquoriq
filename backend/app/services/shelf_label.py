"""
services/shelf_label.py — MODULE 2: LABEL STUDIO (shelf label definition)

A shelf label is the little card a store clips to the shelf edge: bottle name,
rating, price. No photo — just clean, readable, printable type. This module
defines what a label IS (sizes, themes, icons, rating kinds) and validates one.

Deliberately NOT a free-form canvas: a structured label with a good template
produces a professional result every time, where dragging text boxes around
produces something that looks homemade. The owner fills in fields; we lay it out.

Pure functions (no DB / no network / no Pillow) → fully unit-tested.
"""

# ── Print sizes (inches → pixels at 300 DPI, so they print sharp) ─────────────
DPI = 300

LABEL_SIZES: dict[str, dict] = {
    "small":  {"key": "small",  "label": "Small shelf tag",  "inches": (3.5, 2.0), "note": "Business-card size"},
    "medium": {"key": "medium", "label": "Standard talker",  "inches": (4.0, 3.0), "note": "The usual shelf talker"},
    "tall":   {"key": "tall",   "label": "Tall talker",      "inches": (3.0, 5.0), "note": "Narrow shelf strips"},
    "large":  {"key": "large",  "label": "Large card",       "inches": (5.0, 7.0), "note": "Endcaps & displays"},
}
DEFAULT_SIZE = "medium"


def size_pixels(size_key: str) -> tuple[int, int]:
    """Pixel dimensions for a size key, at print DPI."""
    spec = LABEL_SIZES.get(size_key) or LABEL_SIZES[DEFAULT_SIZE]
    w, h = spec["inches"]
    return int(w * DPI), int(h * DPI)


# ── Themes ────────────────────────────────────────────────────────────────────
# Each theme is a small, deliberate palette. bg/ink/muted/accent + whether the
# card gets a printed border (useful as a cut line on white stock).
THEMES: dict[str, dict] = {
    "classic": {
        "key": "classic", "label": "Classic cream",
        "bg": "#f6efe2", "ink": "#1f1b16", "muted": "#6d6353",
        "accent": "#8b1e3f", "accent_ink": "#ffffff", "border": "#c9bda6",
    },
    "bold": {
        "key": "bold", "label": "Bold red",
        "bg": "#ffffff", "ink": "#141414", "muted": "#6b6b6b",
        "accent": "#c1121f", "accent_ink": "#ffffff", "border": "#e0e0e0",
    },
    "premium": {
        "key": "premium", "label": "Premium black & gold",
        "bg": "#14110e", "ink": "#f7f2e7", "muted": "#a89c85",
        "accent": "#c9a227", "accent_ink": "#14110e", "border": "#3a3226",
    },
    "chalkboard": {
        "key": "chalkboard", "label": "Chalkboard",
        "bg": "#22282a", "ink": "#f4f7f5", "muted": "#9fb0ac",
        "accent": "#7fb069", "accent_ink": "#12201a", "border": "#3b4547",
    },
    "minimal": {
        "key": "minimal", "label": "Minimal white",
        "bg": "#ffffff", "ink": "#1a1a1a", "muted": "#8a8a8a",
        "accent": "#1d3557", "accent_ink": "#ffffff", "border": "#dcdcdc",
    },
}
DEFAULT_THEME = "bold"


# ── Icons ─────────────────────────────────────────────────────────────────────
# The owner asked for a bottle/glass emoji. Emoji CANNOT be used: our bundled
# DejaVu fonts have no emoji glyphs, so 🍾 renders as an empty tofu box on the
# print. Instead we draw the same idea as clean vector art, which also prints
# far better at 300 DPI. The `emoji` field here is only the picker's UI hint.
ICONS: dict[str, dict] = {
    "none":       {"key": "none",       "label": "No icon",     "emoji": ""},
    "bottle":     {"key": "bottle",     "label": "Bottle",      "emoji": "🍾"},
    "wine":       {"key": "wine",       "label": "Wine glass",  "emoji": "🍷"},
    "tumbler":    {"key": "tumbler",    "label": "Whiskey glass", "emoji": "🥃"},
    "cocktail":   {"key": "cocktail",   "label": "Cocktail",    "emoji": "🍸"},
    "barrel":     {"key": "barrel",     "label": "Barrel",      "emoji": "🛢"},
}
DEFAULT_ICON = "none"


# ── Ratings ───────────────────────────────────────────────────────────────────
RATING_KINDS = {"none", "stars", "points"}
STARS_MAX = 5.0
POINTS_MIN, POINTS_MAX = 50.0, 100.0

# ── Field limits ──────────────────────────────────────────────────────────────
NAME_MAX = 60
PRICE_MAX = 16
TAGLINE_MAX = 22
DETAIL_MAX = 28
DETAILS_MAX_ITEMS = 3
SOURCE_MAX = 18


def _text(value, limit: str | int, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()[: int(limit)]


def _clamp(value, lo: float, hi: float, default: float) -> float:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return default
    if n != n:                      # NaN would poison JSON and the renderer
        return default
    return min(max(n, lo), hi)


def validate_rating(raw) -> dict:
    """
    Normalize the rating block. Owners pick stars (Vivino-style) or points
    (Wine Spectator / Whisky Advocate style); either can be turned off.
    """
    raw = raw if isinstance(raw, dict) else {}
    kind = raw.get("kind") if raw.get("kind") in RATING_KINDS else "none"
    if kind == "none":
        return {"kind": "none", "value": 0.0, "source": ""}
    if kind == "stars":
        # round to the nearest half — half stars are drawn, quarter stars aren't
        value = round(_clamp(raw.get("value"), 0.0, STARS_MAX, 0.0) * 2) / 2
    else:
        value = round(_clamp(raw.get("value"), POINTS_MIN, POINTS_MAX, POINTS_MIN))
    return {"kind": kind, "value": value, "source": _text(raw.get("source"), SOURCE_MAX)}


def validate_label(raw: dict | None) -> dict:
    """
    Coerce a label spec from the browser into something always renderable.
    Never raises — a hostile or malformed payload degrades to a blank label
    rather than a 500.
    """
    raw = raw if isinstance(raw, dict) else {}

    details = []
    seen = set()
    for item in (raw.get("details") or [])[:DETAILS_MAX_ITEMS * 2]:
        text = _text(item, DETAIL_MAX)
        if text and text.lower() not in seen:
            seen.add(text.lower())
            details.append(text)
        if len(details) >= DETAILS_MAX_ITEMS:
            break

    return {
        "size": raw.get("size") if raw.get("size") in LABEL_SIZES else DEFAULT_SIZE,
        "theme": raw.get("theme") if raw.get("theme") in THEMES else DEFAULT_THEME,
        "icon": raw.get("icon") if raw.get("icon") in ICONS else DEFAULT_ICON,
        "product_name": _text(raw.get("product_name"), NAME_MAX),
        "price": _text(raw.get("price"), PRICE_MAX),
        "was_price": _text(raw.get("was_price"), PRICE_MAX),
        "tagline": _text(raw.get("tagline"), TAGLINE_MAX).upper(),
        "details": details,
        "rating": validate_rating(raw.get("rating")),
        "show_border": bool(raw.get("show_border", True)),
    }


def blank_label(product_name: str = "", price: str = "") -> dict:
    """A fresh label with sensible defaults."""
    return validate_label({"product_name": product_name, "price": price})


def label_summary(label: dict) -> str:
    """Short human name for the saved-label list."""
    name = (label.get("product_name") or "").strip()
    price = (label.get("price") or "").strip()
    if name and price:
        return f"{name} — {price}"
    return name or price or "Untitled label"
