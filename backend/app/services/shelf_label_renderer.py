"""
services/shelf_label_renderer.py — MODULE 2: LABEL STUDIO (rendering)

Draws a shelf label at 300 DPI with Pillow, and lays many of them onto a US
Letter sheet for printing. Same philosophy as the ad text layer: every glyph is
drawn by us, so the price is exactly what the owner typed and nothing is ever
cropped or misspelled.

Label anatomy (vertical rhythm, centred):

    ┌───────────────────────────┐
    │      ▓ STAFF PICK ▓       │  tagline banner (optional)
    │                           │
    │         ╭───╮             │  vector icon (optional)
    │  BUFFALO TRACE BOURBON    │  product name — auto-fit, ≤3 lines
    │      ★★★★☆  Vivino        │  rating: stars or a points badge
    │   90 proof · 750 ML       │  details (optional)
    │                           │
    │        $27.99             │  price — the biggest thing on the card
    │        was $32.99         │  strikethrough (optional)
    └───────────────────────────┘

Emoji are impossible here (DejaVu has no emoji glyphs — 🍾 prints as a tofu
box), so the icons are drawn as vector art instead.
"""

import asyncio
import logging
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.services.shelf_label import ICONS, LABEL_SIZES, THEMES, size_pixels, validate_label

logger = logging.getLogger(__name__)

_FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
_BOLD = str(_FONT_DIR / "DejaVuSans-Bold.ttf")
_REG = str(_FONT_DIR / "DejaVuSans.ttf")

# US Letter at 300 DPI
PAGE_W, PAGE_H = 2550, 3300
PAGE_MARGIN = 150
CUT_GUIDE = (190, 190, 190)


def _hex(color: str) -> tuple[int, int, int]:
    color = (color or "#000000").lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def _fit(draw, text, path, max_w, start, min_size=10):
    """Largest font size at which `text` fits `max_w`. Text is never cropped."""
    size = start
    while size > min_size:
        font = ImageFont.truetype(path, size)
        if draw.textlength(text, font=font) <= max_w:
            return font
        size -= 2
    return ImageFont.truetype(path, min_size)


def _wrap(draw, text, font, max_w, max_lines):
    """Greedy wrap. Marks dropped words with an ellipsis rather than silently
    losing them — a shelf label that quietly renames the product is worse than
    one that visibly ran out of room."""
    words, lines, cur = text.split(), [], ""
    dropped = False
    for i, w in enumerate(words):
        cand = f"{cur} {w}".strip()
        if draw.textlength(cand, font=font) <= max_w:
            cur = cand
        else:
            if cur:
                lines.append(cur)
            cur = w
            if len(lines) == max_lines:
                dropped = i < len(words)
                cur = ""
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    elif cur:
        dropped = True

    if lines and dropped:
        while lines[-1] and draw.textlength(lines[-1] + "…", font=font) > max_w:
            lines[-1] = lines[-1].rsplit(" ", 1)[0] if " " in lines[-1] else lines[-1][:-1]
        lines[-1] += "…"
    if lines and draw.textlength(lines[-1], font=font) > max_w:
        while lines[-1] and draw.textlength(lines[-1] + "…", font=font) > max_w:
            lines[-1] = lines[-1][:-1]
        lines[-1] += "…"
    return lines


def _fit_block(draw, text, path, max_w, max_h, start, max_lines=3, min_size=14):
    """
    Shrink until the wrapped text fits BOTH the width and the height budget.
    Fitting height as well as width is what stops a long bottle name from
    pushing the price off the bottom of the card.
    Returns (font, lines, block_height).
    """
    size = start
    while size > min_size:
        font = ImageFont.truetype(path, size)
        lines = _wrap(draw, text, font, max_w, max_lines)
        step = font.size * 1.14
        fits_w = all(draw.textlength(ln, font=font) <= max_w for ln in lines)
        if fits_w and len(lines) * step <= max_h:
            return font, lines, int(len(lines) * step)
        size -= 2
    font = ImageFont.truetype(path, min_size)
    lines = _wrap(draw, text, font, max_w, max_lines)
    return font, lines, int(len(lines) * font.size * 1.14)


def _center(draw, text, font, cx, y, fill):
    draw.text((cx - draw.textlength(text, font=font) / 2, y), text, font=font, fill=fill)


# ── Vector icons (drawn, not emoji) ───────────────────────────────────────────

def _icon_bottle(d, x, y, w, h, color):
    """Long neck, rounded shoulders — reads as a spirits bottle at small sizes."""
    neck_w = w * 0.34
    cap_w = w * 0.44
    d.rounded_rectangle([x + (w - cap_w) / 2, y, x + (w + cap_w) / 2, y + h * 0.10],
                        radius=w * 0.06, fill=color)
    d.rectangle([x + (w - neck_w) / 2, y + h * 0.07, x + (w + neck_w) / 2, y + h * 0.42],
                fill=color)
    d.rounded_rectangle([x, y + h * 0.36, x + w, y + h], radius=w * 0.26, fill=color)


def _icon_wine(d, x, y, w, h, color):
    bowl_h = h * 0.52
    d.pieslice([x, y - bowl_h * 0.55, x + w, y + bowl_h], start=0, end=180, fill=color)
    d.rectangle([x + w * 0.43, y + bowl_h * 0.85, x + w * 0.57, y + h * 0.88], fill=color)
    d.rounded_rectangle([x + w * 0.14, y + h * 0.88, x + w * 0.86, y + h],
                        radius=h * 0.04, fill=color)


def _icon_tumbler(d, x, y, w, h, color):
    """Rocks glass — a gentle taper, plus a highlight so it reads as glass."""
    d.polygon([(x + w * 0.06, y), (x + w * 0.94, y),
               (x + w * 0.82, y + h), (x + w * 0.18, y + h)], fill=color)
    d.polygon([(x + w * 0.18, y + h * 0.14), (x + w * 0.30, y + h * 0.14),
               (x + w * 0.27, y + h * 0.80), (x + w * 0.17, y + h * 0.80)],
              fill=(255, 255, 255, 70))


def _icon_cocktail(d, x, y, w, h, color):
    d.polygon([(x, y), (x + w, y), (x + w * 0.5, y + h * 0.56)], fill=color)
    d.rectangle([x + w * 0.44, y + h * 0.52, x + w * 0.56, y + h * 0.88], fill=color)
    d.rounded_rectangle([x + w * 0.16, y + h * 0.88, x + w * 0.84, y + h],
                        radius=h * 0.04, fill=color)


def _icon_barrel(d, x, y, w, h, color):
    d.rounded_rectangle([x, y, x + w, y + h], radius=w * 0.30, fill=color)
    band = max(3, int(h * 0.06))
    for fy in (0.26, 0.66):
        d.rectangle([x, y + h * fy, x + w, y + h * fy + band], fill=(255, 255, 255, 80))


_ICON_FNS = {
    "bottle": _icon_bottle, "wine": _icon_wine, "tumbler": _icon_tumbler,
    "cocktail": _icon_cocktail, "barrel": _icon_barrel,
}

# Width ÷ height per icon. A bottle is tall and narrow; a rocks glass is nearly
# square. One shared aspect made the tumbler render as a sliver.
_ICON_ASPECT = {
    "bottle": 0.42, "wine": 0.72, "tumbler": 0.80, "cocktail": 0.88, "barrel": 0.78,
}


def _draw_star(base, cx, cy, r, fill, fraction=1.0):
    """A five-point star; fraction<1 fills only the left part (half stars)."""
    import math
    pts = []
    for i in range(10):
        rad = r if i % 2 == 0 else r * 0.45
        a = math.pi / 5 * i - math.pi / 2
        pts.append((cx + math.cos(a) * rad, cy + math.sin(a) * rad))

    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).polygon(pts, fill=fill)
    if fraction < 1.0:
        mask = Image.new("L", base.size, 0)
        ImageDraw.Draw(mask).rectangle(
            [cx - r, cy - r, cx - r + (2 * r) * fraction, cy + r], fill=255
        )
        layer.putalpha(Image.composite(layer.getchannel("A"),
                                       Image.new("L", base.size, 0), mask))
    base.alpha_composite(layer)


def _render(spec: dict) -> bytes:
    label = validate_label(spec)
    theme = THEMES[label["theme"]]
    W, H = size_pixels(label["size"])

    bg, ink = _hex(theme["bg"]), _hex(theme["ink"])
    muted, accent = _hex(theme["muted"]), _hex(theme["accent"])
    accent_ink, border = _hex(theme["accent_ink"]), _hex(theme["border"])

    img = Image.new("RGBA", (W, H), bg + (255,))
    d = ImageDraw.Draw(img)

    margin = int(W * 0.07)
    inner_w = W - margin * 2
    cx = W / 2

    if label["show_border"]:
        inset = max(3, int(W * 0.012))
        d.rounded_rectangle([inset, inset, W - inset, H - inset],
                            radius=int(W * 0.035), outline=border,
                            width=max(2, int(W * 0.005)))

    # ═══ PASS 1 — MEASURE ════════════════════════════════════════════════════
    # The price is the point of a shelf label, so it gets its space FIRST and is
    # anchored to the bottom (cards then line up neatly along a shelf). Whatever
    # is left is the budget for everything above, and the product name shrinks to
    # fit it. That ordering is why nothing can ever overflow the card.
    price_h = 0
    pf = wf = None
    if label["price"]:
        pf = _fit(d, label["price"], _BOLD, inner_w, int(H * 0.19))
        price_h = int(pf.size * 1.16)
        if label["was_price"]:
            wf = ImageFont.truetype(_REG, int(H * 0.040))
            price_h += int(wf.size * 1.75)

    top_h = H - margin * 2 - price_h - (int(H * 0.02) if price_h else 0)

    rating = label["rating"]
    detail_text = "  ·  ".join(label["details"]) if label["details"] else ""

    # A busy card (tagline + icon + long name + rating + details) can still ask
    # for more room than exists. Rather than let anything collide with the price,
    # give up detail in a fixed priority order — a shelf label must show the name
    # and price above all else. Each pass sheds a little more.
    tag_f = tag_bh = icon_h = icon_w = rate_h = src_h = det_h = 0
    rate_f = src_f = det_f = None
    name_f, name_lines, name_h = None, [], 0

    # Shrink the NAME before shedding elements — a slightly smaller name still
    # reads on a shelf, whereas losing the icon the owner deliberately chose is
    # a visible feature regression. The icon is the last thing to go.
    for step in range(5):
        name_floor = (0.085, 0.066, 0.052, 0.044, 0.038)[step]
        star_scale = (1.0, 1.0, 0.90, 0.82, 0.72)[step]
        det_scale = (1.0, 1.0, 0.94, 0.86, 0.80)[step]
        icon_scale = (1.0, 1.0, 0.82, 0.62, 0.0)[step]
        show_src = (True, True, True, False, False)[step]

        tag_f = tag_bh = 0
        if label["tagline"]:
            tag_f = _fit(d, label["tagline"], _BOLD, inner_w * 0.82, int(H * 0.060))
            tag_bh = int(tag_f.size + H * 0.036) + int(H * 0.026)

        icon_h = icon_w = 0
        if icon_scale and label["icon"] in _ICON_FNS:
            icon_h = int(H * 0.130 * icon_scale)
            icon_w = int(icon_h * _ICON_ASPECT.get(label["icon"], 0.7))

        star_r = int(H * 0.032 * star_scale)
        rate_h = 0
        rate_f = None
        if rating["kind"] == "stars" and rating["value"] > 0:
            rate_h = int(star_r * 2.5)
        elif rating["kind"] == "points" and rating["value"] > 0:
            rate_f = _fit(d, f"{int(rating['value'])} PTS", _BOLD,
                          inner_w * 0.55, int(H * 0.056 * star_scale))
            rate_h = int(rate_f.size + H * 0.028) + int(H * 0.010)

        src_f = src_h = 0
        if rate_h and rating["source"] and show_src:
            src_f = ImageFont.truetype(_REG, int(H * 0.029))
            src_h = int(src_f.size * 1.55)

        det_f = det_h = 0
        if detail_text:
            det_f = _fit(d, detail_text, _REG, inner_w, int(H * 0.038 * det_scale))
            det_h = int(det_f.size * 1.75)

        gaps = (int(H * 0.022) if icon_h else 0) + (int(H * 0.018) if rate_h else 0)
        fixed_h = tag_bh + icon_h + rate_h + src_h + det_h + gaps

        name_f, name_lines, name_h = None, [], 0
        if label["product_name"]:
            name_f, name_lines, name_h = _fit_block(
                d, label["product_name"].upper(), _BOLD, inner_w,
                max(int(H * name_floor), top_h - fixed_h), int(H * 0.105),
                max_lines=3, min_size=max(12, int(H * name_floor)),
            )
            name_h += int(H * 0.016)

        if fixed_h + name_h <= top_h:
            break

    star_r = int(H * 0.032 * (1.0, 1.0, 0.90, 0.82, 0.72)[min(step, 4)])

    # ═══ PASS 2 — PLACE ══════════════════════════════════════════════════════
    content_h = fixed_h + name_h
    y = margin + max(0, (top_h - content_h) // 2)   # optically centred

    if label["tagline"]:
        pad_x, pad_y = int(W * 0.035), int(H * 0.018)
        bw = d.textlength(label["tagline"], font=tag_f) + pad_x * 2
        bh = tag_f.size + pad_y * 2
        d.rounded_rectangle([cx - bw / 2, y, cx + bw / 2, y + bh], radius=bh / 2, fill=accent)
        _center(d, label["tagline"], tag_f, cx, y + pad_y - int(tag_f.size * 0.08), accent_ink)
        y += bh + int(H * 0.026)

    if icon_h:
        _ICON_FNS[label["icon"]](d, cx - icon_w / 2, y, icon_w, icon_h, accent)
        y += icon_h + int(H * 0.022)

    if name_lines:
        step = int(name_f.size * 1.14)
        for line in name_lines:
            _center(d, line, name_f, cx, y, ink)
            y += step
        y += int(H * 0.016)

    if rating["kind"] == "stars" and rating["value"] > 0:
        gap = star_r * 2.45
        sx = cx - (gap * 5) / 2 + star_r
        for i in range(5):
            filled = min(max(rating["value"] - i, 0), 1)
            _draw_star(img, sx + gap * i, y + star_r, star_r, muted + (80,), 1.0)
            if filled > 0:
                _draw_star(img, sx + gap * i, y + star_r, star_r, accent + (255,), filled)
        y += int(star_r * 2.5)
    elif rating["kind"] == "points" and rating["value"] > 0:
        text = f"{int(rating['value'])} PTS"
        pad_x, pad_y = int(W * 0.030), int(H * 0.014)
        bw = d.textlength(text, font=rate_f) + pad_x * 2
        bh = rate_f.size + pad_y * 2
        d.rounded_rectangle([cx - bw / 2, y, cx + bw / 2, y + bh],
                            radius=int(bh * 0.24), fill=accent)
        _center(d, text, rate_f, cx, y + pad_y - int(rate_f.size * 0.08), accent_ink)
        y += bh + int(H * 0.010)

    if src_h:
        _center(d, rating["source"], src_f, cx, y, muted)
        y += src_h
    if rate_h:
        y += int(H * 0.018)

    if det_h:
        _center(d, detail_text, det_f, cx, y, muted)
        y += det_h

    # ── Price, bottom-anchored ──
    if pf:
        py = H - margin - price_h
        _center(d, label["price"], pf, cx, py, accent)
        py += int(pf.size * 1.16)
        if wf:
            was = f"was {label['was_price']}"
            ww = d.textlength(was, font=wf)
            _center(d, was, wf, cx, py, muted)
            ly = py + wf.size * 0.62
            d.line([(cx - ww / 2, ly), (cx + ww / 2, ly)],
                   fill=muted, width=max(2, int(H * 0.004)))

    buf = BytesIO()
    img.convert("RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _render_sheet(specs: list[dict], size_key: str) -> bytes:
    """
    Lay labels onto a US Letter page, left-to-right, with light cut guides.
    All labels on a sheet share one size so the grid is uniform to cut.
    """
    lw, lh = size_pixels(size_key)
    cols = max(1, (PAGE_W - PAGE_MARGIN * 2) // lw)
    rows = max(1, (PAGE_H - PAGE_MARGIN * 2) // lh)
    per_page = cols * rows

    gap_x = (PAGE_W - PAGE_MARGIN * 2 - cols * lw) // max(1, cols - 1) if cols > 1 else 0
    gap_y = (PAGE_H - PAGE_MARGIN * 2 - rows * lh) // max(1, rows - 1) if rows > 1 else 0
    gap_x, gap_y = min(gap_x, 60), min(gap_y, 60)

    pages: list[Image.Image] = []
    for start in range(0, max(1, len(specs)), per_page):
        page = Image.new("RGB", (PAGE_W, PAGE_H), (255, 255, 255))
        pd = ImageDraw.Draw(page)
        for idx, spec in enumerate(specs[start:start + per_page]):
            r, c = divmod(idx, cols)
            x = PAGE_MARGIN + c * (lw + gap_x)
            y = PAGE_MARGIN + r * (lh + gap_y)
            page.paste(Image.open(BytesIO(_render({**spec, "size": size_key}))), (x, y))
            pd.rectangle([x - 1, y - 1, x + lw + 1, y + lh + 1], outline=CUT_GUIDE, width=1)
        pages.append(page)

    buf = BytesIO()
    pages[0].save(buf, format="PDF", resolution=float(300),
                  save_all=True, append_images=pages[1:])
    return buf.getvalue()


async def render_label(spec: dict) -> bytes:
    """One shelf label as PNG bytes (Pillow is CPU-bound → run off the loop)."""
    return await asyncio.to_thread(_render, spec)


async def render_sheet(specs: list[dict], size_key: str) -> bytes:
    """A printable US Letter PDF of many labels, paginated automatically."""
    if not specs:
        raise ValueError("Select at least one label to print.")
    if size_key not in LABEL_SIZES:
        size_key = "medium"
    logger.info("Rendering label sheet: %d labels at size=%s", len(specs), size_key)
    return await asyncio.to_thread(_render_sheet, specs, size_key)


def labels_per_page(size_key: str) -> int:
    """How many fit on one sheet — shown in the UI before printing."""
    lw, lh = size_pixels(size_key)
    cols = max(1, (PAGE_W - PAGE_MARGIN * 2) // lw)
    rows = max(1, (PAGE_H - PAGE_MARGIN * 2) // lh)
    return int(cols * rows)


# Icon keys the renderer can actually draw (the UI hides any it can't)
DRAWABLE_ICONS = {"none", *_ICON_FNS.keys()}
assert DRAWABLE_ICONS <= set(ICONS), "renderer knows an icon the catalogue doesn't"
