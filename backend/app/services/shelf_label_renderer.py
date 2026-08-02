"""
services/shelf_label_renderer.py — MODULE 2: LABEL STUDIO (rendering)

Draws a shelf label at 300 DPI with Pillow and lays many onto a US Letter sheet.

The label is a list of positioned elements, so drawing is one loop. Crucially,
_render also COLLECTS THE BOX it drew each element into and hands those back:
the browser places its drag handles from those boxes, which is what keeps the
editor's hit areas exactly aligned with the print. One renderer, one geometry —
no second layout engine in the browser to drift out of sync.

The house look is copied from the store's own Canva tags: serif type, black on
white, a red sale price, a starburst, "REGULAR / SAVE" spelled out, and small
bottle/barrel clip-art.
"""

import asyncio
import logging
import math
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.services.shelf_label import ACCENTS, ART, LABEL_SIZES, size_pixels, validate_label

logger = logging.getLogger(__name__)

_FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"

_FAMILIES = {
    "serif":     (_FONT_DIR / "DejaVuSerif-Bold.ttf",     _FONT_DIR / "DejaVuSerif.ttf"),
    "serif_alt": (_FONT_DIR / "LiberationSerif-Bold.ttf", _FONT_DIR / "LiberationSerif-Regular.ttf"),
    "sans":      (_FONT_DIR / "DejaVuSans-Bold.ttf",      _FONT_DIR / "DejaVuSans.ttf"),
}

INK = (17, 17, 17)
PAPER = (255, 255, 255)
MUTED = (105, 105, 105)

PAGE_W, PAGE_H = 2550, 3300
PAGE_MARGIN = 150
CUT_GUIDE = (200, 200, 200)


def _fonts(family: str):
    bold, reg = _FAMILIES.get(family) or _FAMILIES["serif"]
    if not bold.exists():
        bold, reg = _FAMILIES["sans"]
    return str(bold), str(reg)


def _hex(color: str):
    color = (color or "#111111").lstrip("#")
    if len(color) == 3:
        color = "".join(c * 2 for c in color)
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def _resolve_color(slot: str, accent_hex: str):
    if slot == "accent":
        return _hex(accent_hex)
    if slot == "paper":
        return PAPER
    if slot == "muted":
        return MUTED
    if isinstance(slot, str) and slot.startswith("#"):
        return _hex(slot)
    return INK


def _wrap(draw, text, font, max_w, max_lines):
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
    if lines and (dropped or draw.textlength(lines[-1], font=font) > max_w):
        while lines[-1] and draw.textlength(lines[-1] + "…", font=font) > max_w:
            lines[-1] = lines[-1][:-1]
        lines[-1] += "…"
    return lines


def _fit_lines(draw, text, path, start_px, max_w, max_lines):
    """
    Shrink until every line fits the width and no word is dropped. Checking the
    width of EVERY line matters: a single long word can't be wrapped away, and
    without this check it renders at full size and runs off the card.
    """
    size = max(int(start_px), 9)
    while size > 8:
        f = ImageFont.truetype(path, size)
        lines = _wrap(draw, text, f, max_w, max_lines)
        complete = not (lines and lines[-1].endswith("…"))
        fits = all(draw.textlength(l, font=f) <= max_w for l in lines)
        if complete and fits:
            return f, lines
        size -= 2
    f = ImageFont.truetype(path, 8)
    return f, _wrap(draw, text, f, max_w, max_lines)


# ── Clip-art (drawn, never emoji — the print fonts have no emoji glyphs) ──────

def _a_bottle(d, x, y, w, h, c):
    d.rounded_rectangle([x + w * 0.28, y, x + w * 0.72, y + h * 0.11], radius=w * 0.08, fill=c)
    d.rectangle([x + w * 0.34, y + h * 0.08, x + w * 0.66, y + h * 0.40], fill=c)
    d.rounded_rectangle([x, y + h * 0.34, x + w, y + h], radius=w * 0.26, fill=c)


def _a_bottles(d, x, y, w, h, c):
    bw = w * 0.19
    for bx, bh in ((0.02, 0.74), (0.26, 0.94), (0.50, 0.64)):
        left, top = x + w * bx, y + h * (1 - bh)
        d.rectangle([left + bw * 0.34, top, left + bw * 0.66, top + h * bh * 0.32], fill=c)
        d.rounded_rectangle([left, top + h * bh * 0.26, left + bw, y + h], radius=bw * 0.24, fill=c)
    gx, gw = x + w * 0.74, w * 0.24
    d.polygon([(gx, y + h * 0.30), (gx + gw, y + h * 0.30), (gx + gw * 0.5, y + h * 0.70)], fill=c)
    d.rectangle([gx + gw * 0.44, y + h * 0.66, gx + gw * 0.56, y + h * 0.92], fill=c)
    d.rectangle([gx + gw * 0.22, y + h * 0.92, gx + gw * 0.78, y + h], fill=c)


def _a_barrel(d, x, y, w, h, c):
    d.rounded_rectangle([x, y, x + w, y + h], radius=w * 0.34, fill=c)
    hoop = max(2, int(h * 0.055))
    for fy in (0.26, 0.62):
        d.rectangle([x - 1, y + h * fy, x + w + 1, y + h * fy + hoop], fill=PAPER)
    d.ellipse([x + w * 0.14, y - h * 0.03, x + w * 0.86, y + h * 0.16],
              outline=PAPER, width=max(2, int(w * 0.07)))


def _a_grapes(d, x, y, w, h, c):
    r = w * 0.15
    for row, count in enumerate((3, 2, 1)):
        for i in range(count):
            cx = x + w * 0.5 + (i - (count - 1) / 2) * r * 2.05
            cy = y + h * 0.34 + row * r * 1.7
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c)
    d.line([(x + w * 0.5, y), (x + w * 0.5, y + h * 0.22)], fill=c, width=max(2, int(w * 0.06)))


def _a_wineglass(d, x, y, w, h, c):
    d.pieslice([x, y - h * 0.26, x + w, y + h * 0.52], start=0, end=180, fill=c)
    d.rectangle([x + w * 0.43, y + h * 0.44, x + w * 0.57, y + h * 0.88], fill=c)
    d.rounded_rectangle([x + w * 0.14, y + h * 0.88, x + w * 0.86, y + h], radius=h * 0.04, fill=c)


def _a_martini(d, x, y, w, h, c):
    d.polygon([(x, y), (x + w, y), (x + w * 0.5, y + h * 0.56)], fill=c)
    d.rectangle([x + w * 0.44, y + h * 0.52, x + w * 0.56, y + h * 0.88], fill=c)
    d.rounded_rectangle([x + w * 0.16, y + h * 0.88, x + w * 0.84, y + h], radius=h * 0.04, fill=c)


def _a_beer(d, x, y, w, h, c):
    d.rounded_rectangle([x, y + h * 0.10, x + w * 0.72, y + h], radius=w * 0.09, fill=c)
    d.arc([x + w * 0.60, y + h * 0.28, x + w, y + h * 0.78], start=270, end=90,
          fill=c, width=max(3, int(w * 0.10)))
    d.ellipse([x - w * 0.02, y, x + w * 0.34, y + h * 0.22], fill=c)
    d.ellipse([x + w * 0.30, y - h * 0.03, x + w * 0.74, y + h * 0.20], fill=c)


def _a_star(d, x, y, w, h, c):
    cx, cy, r = x + w / 2, y + h / 2, min(w, h) / 2
    pts = []
    for i in range(10):
        rad = r if i % 2 == 0 else r * 0.45
        a = math.pi / 5 * i - math.pi / 2
        pts.append((cx + math.cos(a) * rad, cy + math.sin(a) * rad))
    d.polygon(pts, fill=c)


def _a_laurel(d, x, y, w, h, c):
    """Two leafy sprigs curving up into a wreath — a classic award flourish."""
    cx, base = x + w / 2, y + h * 0.94
    lw = max(2, int(h * 0.055))
    for side in (-1, 1):
        # Stem: a shallow arc from the base up and outwards
        prev = (cx, base)
        for i in range(1, 9):
            t = i / 8
            px = cx + side * w * 0.42 * math.sin(t * 1.35)
            py = base - h * 0.80 * t
            d.line([prev, (px, py)], fill=c, width=lw)
            prev = (px, py)
            if i % 2 == 0:                      # a leaf every other step
                r = h * (0.15 - 0.07 * t)
                d.ellipse([px - r * 0.85, py - r * 0.55, px + r * 0.85, py + r * 0.55], fill=c)


def _a_flourish(d, x, y, w, h, c):
    lw = max(2, int(h * 0.20))
    d.line([(x + w * 0.10, y + h * 0.5), (x + w * 0.90, y + h * 0.5)], fill=c, width=lw)
    r = h * 0.42
    d.ellipse([x + w * 0.45, y + h * 0.5 - r, x + w * 0.55, y + h * 0.5 + r], fill=c)
    for fx in (0.06, 0.94):
        d.ellipse([x + w * fx - r * 0.3, y + h * 0.5 - r * 0.3,
                   x + w * fx + r * 0.3, y + h * 0.5 + r * 0.3], fill=c)


def _a_snowflake(d, x, y, w, h, c):
    cx, cy, r = x + w / 2, y + h / 2, min(w, h) / 2
    lw = max(2, int(r * 0.14))
    for i in range(6):
        a = math.pi / 3 * i
        ex, ey = cx + math.cos(a) * r, cy + math.sin(a) * r
        d.line([(cx, cy), (ex, ey)], fill=c, width=lw)
        for t in (0.55, 0.80):
            bx, by = cx + math.cos(a) * r * t, cy + math.sin(a) * r * t
            for sign in (-1, 1):
                b = a + sign * math.pi / 4
                d.line([(bx, by), (bx + math.cos(b) * r * 0.22, by + math.sin(b) * r * 0.22)],
                       fill=c, width=max(1, lw // 2))


_ART_FNS = {
    "bottle": _a_bottle, "bottles": _a_bottles, "barrel": _a_barrel,
    "grapes": _a_grapes, "wineglass": _a_wineglass, "martini": _a_martini,
    "beer": _a_beer, "star": _a_star, "laurel": _a_laurel,
    "flourish": _a_flourish, "snowflake": _a_snowflake,
}


def _starburst(d, cx, cy, r, fill, points=12, inner=0.72):
    pts = []
    for i in range(points * 2):
        rad = r if i % 2 == 0 else r * inner
        a = math.pi / points * i - math.pi / 2
        pts.append((cx + math.cos(a) * rad, cy + math.sin(a) * rad))
    d.polygon(pts, fill=fill)


# ── Element drawing ───────────────────────────────────────────────────────────

def _draw_element(img, d, el, W, H, bold, reg, accent_hex) -> tuple:
    """Draw one element; return the (x, y, w, h) box it occupied, in pixels."""
    x, y = el["x"] * W, el["y"] * H
    w = el["w"] * W
    color = _resolve_color(el["color"], accent_hex)
    kind = el["kind"]

    if kind == "art":
        aspect = ART.get(el["art"], {}).get("aspect", 1.0)
        h = w / max(aspect, 0.05)
        fn = _ART_FNS.get(el["art"])
        if fn:
            layer = Image.new("RGBA", (max(2, int(w)) + 4, max(2, int(h)) + 4), (0, 0, 0, 0))
            fn(ImageDraw.Draw(layer), 2, 2, w, h, color + (255,))
            if el["rotation"]:
                layer = layer.rotate(-el["rotation"], expand=True, resample=Image.BICUBIC)
            img.paste(layer, (int(x), int(y)), layer)
        return (x, y, w, h)

    if kind == "line":
        thick = max(2, int(el["size"] * H))
        d.rectangle([x, y, x + w, y + thick], fill=color)
        return (x, y, w, thick)

    text = el["text"]
    if not text:
        return (x, y, w, el["size"] * H)

    path = bold if el["bold"] else reg
    start_px = el["size"] * H

    if kind == "starburst":
        r = w / 2
        _starburst(d, x + r, y + r, r, _resolve_color("accent", accent_hex))
        f, lines = _fit_lines(d, text, path, start_px, w * 0.86, 1)
        d.text((x + r - d.textlength(lines[0], font=f) / 2, y + r - f.size * 0.62),
               lines[0], font=f, fill=color)
        return (x, y, w, w)

    if kind == "banner":
        # A filled column/strip with the text stacked down it (the DEAL bookends)
        bh = H
        d.rectangle([x, y, x + w, y + bh], fill=_resolve_color("accent", accent_hex))
        f = ImageFont.truetype(path, max(9, int(el["size"] * H)))
        letters = list(text)
        step = bh / (len(letters) + 1) if letters else bh
        for i, ch in enumerate(letters):
            d.text((x + w / 2 - d.textlength(ch, font=f) / 2,
                    step * (i + 1) - f.size * 0.6), ch, font=f, fill=color)
        return (x, y, w, bh)

    # text / price
    f, lines = _fit_lines(d, text, path, start_px, w, el["lines"])
    step = f.size * 1.12
    total_h = step * len(lines)

    if el["rotation"]:
        pad = int(max(w, total_h))
        layer = Image.new("RGBA", (int(w) + pad, int(total_h) + pad), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        for i, line in enumerate(lines):
            lx = {"left": 0, "center": (w - ld.textlength(line, font=f)) / 2,
                  "right": w - ld.textlength(line, font=f)}[el["align"]]
            ld.text((lx, i * step), line, font=f, fill=color + (255,))
        layer = layer.rotate(-el["rotation"], expand=True, resample=Image.BICUBIC)
        img.paste(layer, (int(x), int(y)), layer)
    else:
        for i, line in enumerate(lines):
            lx = {"left": x, "center": x + (w - d.textlength(line, font=f)) / 2,
                  "right": x + w - d.textlength(line, font=f)}[el["align"]]
            d.text((lx, y + i * step), line, font=f, fill=color)

    return (x, y, w, total_h)


def _render(spec: dict, scale: float = 1.0, with_boxes: bool = False):
    """
    Draw the label. When with_boxes is set, also return each element's box in
    RELATIVE units — the browser positions its drag handles from these, which is
    what keeps the editor aligned with the print.
    """
    L = validate_label(spec)
    W, H = size_pixels(L["size"])
    if scale != 1.0:
        W, H = max(80, int(W * scale)), max(80, int(H * scale))

    bold, reg = _fonts(L["font"])
    accent_hex = ACCENTS.get(L["accent"], ACCENTS["red"])["hex"]

    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)

    boxes = []
    for el in L["elements"]:
        if not el["visible"]:
            continue
        try:
            bx, by, bw, bh = _draw_element(img, d, el, W, H, bold, reg, accent_hex)
        except Exception:  # noqa: BLE001 — one bad element must not kill the label
            logger.warning("element failed to draw: %s", el.get("id"), exc_info=True)
            continue
        if with_boxes:
            boxes.append({"id": el["id"], "kind": el["kind"],
                          "x": bx / W, "y": by / H,
                          "w": bw / W, "h": max(bh, H * 0.03) / H})

    if L["show_border"]:
        inset = max(2, int(W * 0.008))
        d.rectangle([inset, inset, W - inset, H - inset], outline=INK,
                    width=max(2, int(W * 0.005)))

    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    png = buf.getvalue()
    return (png, boxes, (W, H)) if with_boxes else png


def _render_sheet(specs: list[dict], size_key: str) -> bytes:
    lw, lh = size_pixels(size_key)
    cols = max(1, (PAGE_W - PAGE_MARGIN * 2) // lw)
    rows = max(1, (PAGE_H - PAGE_MARGIN * 2) // lh)
    per_page = cols * rows

    gap_x = (PAGE_W - PAGE_MARGIN * 2 - cols * lw) // max(1, cols - 1) if cols > 1 else 0
    gap_y = (PAGE_H - PAGE_MARGIN * 2 - rows * lh) // max(1, rows - 1) if rows > 1 else 0
    gap_x, gap_y = min(gap_x, 60), min(gap_y, 60)

    pages: list[Image.Image] = []
    for start in range(0, max(1, len(specs)), per_page):
        page = Image.new("RGB", (PAGE_W, PAGE_H), PAPER)
        pd = ImageDraw.Draw(page)
        for idx, spec in enumerate(specs[start:start + per_page]):
            r, c = divmod(idx, cols)
            x = PAGE_MARGIN + c * (lw + gap_x)
            y = PAGE_MARGIN + r * (lh + gap_y)
            page.paste(Image.open(BytesIO(_render({**spec, "size": size_key}))), (x, y))
            pd.rectangle([x - 1, y - 1, x + lw + 1, y + lh + 1], outline=CUT_GUIDE, width=1)
        pages.append(page)

    buf = BytesIO()
    pages[0].save(buf, format="PDF", resolution=300.0, save_all=True,
                  append_images=pages[1:])
    return buf.getvalue()


async def render_label(spec: dict) -> bytes:
    return await asyncio.to_thread(_render, spec)


async def render_preview(spec: dict, scale: float = 0.42):
    """Smaller render for the editor, plus the boxes for its drag handles."""
    return await asyncio.to_thread(_render, spec, scale, True)


async def render_sheet(specs: list[dict], size_key: str) -> bytes:
    if not specs:
        raise ValueError("Select at least one label to print.")
    if size_key not in LABEL_SIZES:
        size_key = "medium"
    logger.info("Rendering label sheet: %d labels at size=%s", len(specs), size_key)
    return await asyncio.to_thread(_render_sheet, specs, size_key)


def labels_per_page(size_key: str) -> int:
    lw, lh = size_pixels(size_key)
    cols = max(1, (PAGE_W - PAGE_MARGIN * 2) // lw)
    rows = max(1, (PAGE_H - PAGE_MARGIN * 2) // lh)
    return int(cols * rows)


assert set(_ART_FNS) == set(ART), "an art piece is advertised but not drawable"
