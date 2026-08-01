"""
services/ad_text_renderer.py — MODULE 1: AI AD CREATOR (deterministic text layer)

The image model paints the scene; THIS module typesets the words. Every character
on a finished LiquorIQ ad is drawn here with Pillow, which means the price is
exactly what the owner typed and nothing is ever cropped or misspelled.

DESIGN RULES (learned the hard way — v1 flattened half the artwork under a dark
gradient and used the same white-on-black treatment for every ad, which read as
a template rather than a designed piece):
  · SHOW THE PHOTO. Type sits in a contained band or a narrow rail, never a
    blanket over half the frame. Bands are FROSTED (blur the pixels underneath)
    so the artwork still reads through instead of being hidden.
  · USE THE AD'S OWN COLOUR. The AI picks an accent hex to match the scene it
    art-directed, so each ad's typography belongs to that ad.
  · LOOK ART-DIRECTED. Tracked-out eyebrow, a hairline accent rule, tight
    leading, and a real price lockup — not centred defaults.

Three layouts:
  rail   — narrow left column over a soft gradient (portrait / poster)
  band   — frosted band across the bottom, headline left + price right (square)
  banner — frosted strip at the top, price medallion at the bottom (landscape)
"""

import asyncio
import logging
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

logger = logging.getLogger(__name__)

_FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
_BOLD = str(_FONT_DIR / "DejaVuSans-Bold.ttf")
_REG = str(_FONT_DIR / "DejaVuSans.ttf")

WHITE = (255, 255, 255, 255)
SOFT = (236, 232, 226, 255)
# Warm off-white reads as "designed"; pure white reads as "system default".
CREAM = (245, 239, 228, 255)
LAYOUTS = ("poster", "rail", "band", "banner")


def _hex(color: str, alpha: int = 255):
    color = (color or "#c1121f").lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4)) + (alpha,)


def _readable_on(rgb) -> tuple:
    """Black or white text, whichever survives on this accent (WCAG-ish luma)."""
    r, g, b = rgb[:3]
    return (17, 17, 17, 255) if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else WHITE


def _fit(draw, text, path, max_w, start, min_size=10):
    size = start
    while size > min_size:
        f = ImageFont.truetype(path, size)
        if draw.textlength(text, font=f) <= max_w:
            return f
        size -= 2
    return ImageFont.truetype(path, min_size)


def _wrap(draw, text, font, max_w, max_lines):
    """
    Greedy wrap that MARKS dropped words with an ellipsis. Silent truncation is
    the dangerous failure here — "FIRE UP THE LONG WEEKEND" quietly becoming
    "FIRE UP THE LONG" changes the message and nobody notices.
    """
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


def _fit_block(draw, text, path, max_w, max_h, start, max_lines=3, min_size=16):
    """
    Fit width AND height, and keep shrinking while any word is being dropped —
    so the whole headline survives rather than being quietly cut short.
    """
    size = start
    while size > min_size:
        f = ImageFont.truetype(path, size)
        lines = _wrap(draw, text, f, max_w, max_lines)
        complete = not (lines and lines[-1].endswith("…"))
        # EVERY line must fit the width. Checking only "was anything dropped"
        # let a single long word ("CELEBRATION") through at full size and run
        # straight over the product.
        fits_w = all(draw.textlength(l, font=f) <= max_w for l in lines)
        if fits_w and complete and len(lines) * f.size * 1.1 <= max_h:
            return f, lines, int(len(lines) * f.size * 1.1)
        size -= 2
    f = ImageFont.truetype(path, min_size)
    lines = _wrap(draw, text, f, max_w, max_lines)
    return f, lines, int(len(lines) * f.size * 1.1)


def _tracked(draw, text, font, x, y, fill, tracking):
    """Letter-spaced text — the single cheapest way to make type look designed."""
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + tracking
    return x


def _tracked_width(draw, text, font, tracking):
    return sum(draw.textlength(c, font=font) for c in text) + tracking * max(0, len(text) - 1)


def _frost(base: Image.Image, box, darken=120, blur=18):
    """
    Frosted panel: blur the photo underneath and tint it. The artwork still shows
    through, so the ad reads as one composition instead of a caption stuck on top.
    """
    x0, y0, x1, y1 = (int(v) for v in box)
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(base.width, x1), min(base.height, y1)
    if x1 <= x0 or y1 <= y0:
        return
    region = base.crop((x0, y0, x1, y1)).filter(ImageFilter.GaussianBlur(blur))
    tint = Image.new("RGBA", region.size, (10, 10, 14, darken))
    base.paste(Image.alpha_composite(region.convert("RGBA"), tint), (x0, y0))


def _gradient_rail(base: Image.Image, width: int, strength=165):
    """A soft left-to-right fade — only as wide as the type actually needs."""
    W, H = base.size
    grad = Image.new("L", (W, 1), 0)
    px = grad.load()
    for x in range(W):
        if x <= width * 0.55:
            px[x, 0] = strength
        elif x < width:
            px[x, 0] = int(strength * (1 - (x - width * 0.55) / (width * 0.45)))
        else:
            px[x, 0] = 0
    scrim = Image.new("RGBA", (W, H), (8, 8, 12, 255))
    scrim.putalpha(grad.resize((W, H)))
    base.alpha_composite(scrim.filter(ImageFilter.GaussianBlur(max(2, W // 500))))


def _condensed(base, text, font, x, y, fill, squeeze=0.88, shadow=True):
    """
    Draw horizontally-compressed text.

    Poster headlines want a heavy CONDENSED face; we only ship DejaVu Sans Bold.
    Rendering to a layer and squashing it horizontally gets most of the way there
    and costs nothing — the difference between "designed" and "default" type.
    Returns the drawn width.
    """
    tmp = Image.new("RGBA", (max(1, int(font.size * len(text) * 1.2) + 40),
                             int(font.size * 1.7)), (0, 0, 0, 0))
    ImageDraw.Draw(tmp).text((0, 0), text, font=font, fill=fill)
    bbox = tmp.getbbox()
    if not bbox:
        return 0
    tmp = tmp.crop((0, 0, bbox[2] + 2, tmp.height))
    new_w = max(1, int(tmp.width * squeeze))
    tmp = tmp.resize((new_w, tmp.height), Image.LANCZOS)

    if shadow:
        sh = Image.new("RGBA", tmp.size, (0, 0, 0, 0))
        sh.putalpha(tmp.getchannel("A").point(lambda a: int(a * 0.55)))
        sh = sh.filter(ImageFilter.GaussianBlur(max(2, font.size // 14)))
        base.alpha_composite(sh, (int(x), int(y + font.size * 0.06)))
    base.alpha_composite(tmp, (int(x), int(y)))
    return new_w


def _condensed_width(draw, text, font, squeeze=0.88):
    return draw.textlength(text, font=font) * squeeze


def _corner_wash(base, w_frac=0.68, h_frac=0.62, strength=104):
    """
    A gentle darkening that fades out both right and down from the top-left.
    Just enough to guarantee the headline stays legible on a bright scene —
    NOT the half-frame blanket that made v1 look like a template.
    """
    W, H = base.size
    gw, gh = max(2, int(W * w_frac)), max(2, int(H * h_frac))
    horiz = Image.new("L", (gw, 1))
    hp = horiz.load()
    for x in range(gw):
        hp[x, 0] = int(strength * (1 - (x / gw) ** 1.35))
    vert = Image.new("L", (1, gh))
    vp = vert.load()
    for y in range(gh):
        vp[0, y] = int(255 * (1 - (y / gh) ** 1.6))

    mask = Image.new("L", (W, H), 0)
    corner = Image.composite(
        horiz.resize((gw, gh)),
        Image.new("L", (gw, gh), 0),
        vert.resize((gw, gh)),
    )
    mask.paste(corner, (0, 0))
    scrim = Image.new("RGBA", (W, H), (10, 10, 14, 255))
    scrim.putalpha(mask.filter(ImageFilter.GaussianBlur(W // 60)))
    base.alpha_composite(scrim)


def _brushstroke(base, box, color, seed=0):
    """
    A hand-painted brush mark behind the offer — the signature element of a
    premium spirits poster. A plain rounded rectangle reads as a UI button; an
    irregular painted edge reads as art direction.

    Built deterministically (seeded) so regenerating the same ad is reproducible:
    a body rectangle, wavy top/bottom edges from overlapping ellipses, tapered
    ends, and a couple of dry-brush specks.
    """
    import random

    x0, y0, x1, y1 = (int(v) for v in box)
    w, h = max(1, x1 - x0), max(1, y1 - y0)
    pad = int(h * 0.5)
    layer = Image.new("L", (w + pad * 2, h + pad * 2), 0)
    d = ImageDraw.Draw(layer)
    ox, oy = pad, pad

    rng = random.Random(seed)
    d.rounded_rectangle([ox, oy + h * 0.10, ox + w, oy + h * 0.90],
                        radius=int(h * 0.20), fill=255)

    # Wavy edges: overlapping ellipses of varying height along the top and bottom
    steps = max(8, w // int(h * 0.45))
    for i in range(steps + 1):
        px = ox + w * i / steps
        rw = h * rng.uniform(0.24, 0.38)
        top = oy + h * (0.10 - rng.uniform(0.0, 0.045))
        bot = oy + h * (0.90 + rng.uniform(0.0, 0.045))
        d.ellipse([px - rw, top, px + rw, top + h * rng.uniform(0.22, 0.32)], fill=255)
        d.ellipse([px - rw, bot - h * rng.uniform(0.22, 0.32), px + rw, bot], fill=255)

    # Tapered ends — a brush lifts off rather than stopping square
    d.polygon([(ox, oy + h * 0.26), (ox - h * 0.26, oy + h * 0.52),
               (ox, oy + h * 0.76)], fill=255)
    d.polygon([(ox + w, oy + h * 0.22), (ox + w + h * 0.32, oy + h * 0.50),
               (ox + w, oy + h * 0.80)], fill=255)

    # Dry-brush specks trailing off the trailing end
    for _ in range(2):
        sx = ox + w + h * rng.uniform(0.34, 0.52)
        sy = oy + h * rng.uniform(0.34, 0.68)
        sr = h * rng.uniform(0.035, 0.07)
        d.ellipse([sx - sr, sy - sr * 0.6, sx + sr, sy + sr * 0.6], fill=255)

    layer = layer.filter(ImageFilter.GaussianBlur(max(1, h // 40)))
    layer = layer.point(lambda a: 255 if a > 118 else 0)   # crisp painted edge

    paint = Image.new("RGBA", layer.size, tuple(color[:3]) + (255,))
    paint.putalpha(layer)
    base.alpha_composite(paint, (x0 - pad, y0 - pad))


# ── Shared pieces ─────────────────────────────────────────────────────────────

def _price_lockup(d, base, x, y, price, accent, size, align="left", pad_ratio=0.36):
    """The price in a solid accent block — the ad's second focal point."""
    f = ImageFont.truetype(_BOLD, size)
    tw = d.textlength(price, font=f)
    pad_x, pad_y = int(size * pad_ratio), int(size * 0.22)
    bw, bh = tw + pad_x * 2, size + pad_y * 2
    bx = x if align == "left" else x - bw
    d.rounded_rectangle([bx, y, bx + bw, y + bh], radius=int(bh * 0.16), fill=accent)
    d.text((bx + pad_x, y + pad_y - int(size * 0.08)), price, font=f, fill=_readable_on(accent))
    return bw, bh


def _store_footer(d, x, y, store, accent, size, align="left", max_w=99999):
    f = ImageFont.truetype(_BOLD, size)
    text = _wrap(d, store, f, max_w, 1)[0] if store else ""
    if not text:
        return
    w = _tracked_width(d, text, f, size * 0.10)
    sx = x if align == "left" else x - w
    d.line([(sx, y - size * 0.55), (sx + min(w, size * 3.2), y - size * 0.55)],
           fill=accent, width=max(2, size // 9))
    _tracked(d, text, f, sx, y, WHITE, size * 0.10)


# ── Layouts ───────────────────────────────────────────────────────────────────

def _layout_poster(base, d, spec, accent):
    """
    Premium spirits poster: a big condensed headline top-left straight over the
    photograph, and the offer in a hand-painted brush mark bottom-left. No panel
    and no half-frame scrim — just a soft corner wash for legibility, so the
    artwork carries the ad.
    """
    W, H = base.size
    margin = int(W * 0.062)
    text_w = int(W * 0.56)
    squeeze = 0.88

    _corner_wash(base, w_frac=0.70, h_frac=0.66, strength=104)

    y = int(H * 0.075)   # a real top margin — the headline is never clipped

    if spec.get("eyebrow"):
        ef = ImageFont.truetype(_BOLD, int(H * 0.024))
        _tracked(d, spec.get("eyebrow", ""), ef, margin, y,
                 _hex(accent)[:3] + (255,), ef.size * 0.36)
        y += int(ef.size * 2.2)

    # Headline — the dominant element, tight leading like a real poster
    headline = (spec.get("headline") or "").upper()
    if headline:
        hf, hlines, _ = _fit_block(
            d, headline, _BOLD, text_w / squeeze, int(H * 0.44),
            int(H * 0.115), max_lines=4, min_size=int(H * 0.05),
        )
        for line in hlines:
            _condensed(base, line, hf, margin, y, CREAM, squeeze)
            y += int(hf.size * 1.03)
        y += int(H * 0.022)

    if spec.get("subheadline"):
        sf = ImageFont.truetype(_BOLD, int(H * 0.042))
        for line in _wrap(d, spec.get("subheadline", "").upper(), sf,
                          text_w / squeeze, 2):
            _condensed(base, line, sf, margin, y, CREAM, squeeze)
            y += int(sf.size * 1.16)
        y += int(H * 0.012)

    if spec.get("details"):
        df = ImageFont.truetype(_REG, int(H * 0.026))
        line = _wrap(d, "   ·   ".join(spec.get("details", [])[:3]), df, text_w, 1)[0]
        d.text((margin, y), line, font=df, fill=SOFT)

    # ── Offer, in the brush mark ──
    price = spec.get("price") or ""
    if price:
        product = (spec.get("product") or "").upper()
        # The brush mark is narrower than the headline column: its tapered ends
        # add ~8% of the frame, and it must still stop short of the product.
        offer_w = int(W * 0.42)

        lbl_f = ImageFont.truetype(_BOLD, int(H * 0.032))
        at_f = ImageFont.truetype(_BOLD, int(H * 0.046))
        price_f = _fit(d, price, _BOLD, offer_w / squeeze, int(H * 0.098))

        # Shrink the product name to fit rather than chopping it to "LAMARCA…".
        # A truncated product name on an ad is worse than a smaller one.
        prod_f = _fit(d, product, _BOLD, offer_w / squeeze,
                      int(H * 0.046), min_size=int(H * 0.024)) if product else None

        # If the "price" is really just the product restated, drop the extra row.
        if product and product.lower()[:12] in price.lower():
            product = ""

        rows = [("label", "OFFER", lbl_f)]
        if product:
            rows.append(("plain", product, prod_f))
        rows.append(("price", price, price_f))

        # "AT $21.99" reads naturally; "AT 20% OFF" does not.
        use_at = bool(product) and spec.get("price_is_amount", price.startswith("$"))

        gap = int(H * 0.006)
        block_h = sum(int(f.size * 1.10) for _, _, f in rows) + gap * (len(rows) - 1)
        widths = []
        for kind, text, f in rows:
            w = _condensed_width(d, text, f, squeeze)
            if kind == "price" and use_at:
                w += _condensed_width(d, "AT ", at_f, squeeze)
            widths.append(w)
        block_w = min(max(widths), offer_w)

        pad_x, pad_y = int(H * 0.036), int(H * 0.028)
        bx0 = margin
        by1 = H - int(H * 0.085)
        by0 = by1 - block_h - pad_y * 2
        _brushstroke(base, (bx0, by0, bx0 + block_w + pad_x * 2, by1),
                     _hex(accent), seed=abs(hash(price)) % 10_000)

        # Ink must contrast with the brush colour — cream on a gold stroke is
        # unreadable, so light accents get dark type.
        ink = _readable_on(_hex(accent))
        ink = CREAM if ink == WHITE else ink

        ty = by0 + pad_y
        tx = bx0 + pad_x
        for kind, text, f in rows:
            if kind == "price" and use_at:
                w = _condensed(base, "AT ", at_f, tx,
                               ty + (f.size - at_f.size) * 0.62, ink, squeeze, shadow=False)
                _condensed(base, text, f, tx + w, ty, ink, squeeze, shadow=False)
            else:
                _condensed(base, text, f, tx, ty, ink, squeeze, shadow=False)
            ty += int(f.size * 1.10) + gap

    # Store name, discreet, bottom-right
    if spec.get("store_name"):
        sf = ImageFont.truetype(_BOLD, int(H * 0.024))
        text = _wrap(d, spec["store_name"], sf, int(W * 0.42), 1)[0]
        w = _tracked_width(d, text, sf, sf.size * 0.12)
        _tracked(d, text, sf, W - margin - w, H - margin - sf.size,
                 CREAM, sf.size * 0.12)


def _layout_rail(base, d, spec, accent):
    """Narrow left column. For posters/portrait, where vertical room is cheap."""
    W, H = base.size
    margin = int(W * 0.065)
    rail_w = int(W * 0.46)
    _gradient_rail(base, int(W * 0.60))

    inner = rail_w - margin
    blocks = []

    if spec.get("eyebrow"):
        ef = ImageFont.truetype(_BOLD, int(H * 0.021))
        blocks.append(("eyebrow", ef, spec.get("eyebrow", ""), int(ef.size * 2.4)))

    hf, hlines, hh = _fit_block(d, spec.get("headline", "").upper(), _BOLD, inner,
                                int(H * 0.34), int(H * 0.082), max_lines=3)
    blocks.append(("headline", hf, hlines, hh + int(H * 0.018)))

    if spec.get("subheadline"):
        sf = ImageFont.truetype(_REG, int(H * 0.027))
        slines = _wrap(d, spec.get("subheadline", ""), sf, inner, 2)
        blocks.append(("sub", sf, slines, int(len(slines) * sf.size * 1.35) + int(H * 0.022)))

    for det in (spec.get("details") or [])[:3]:
        df = ImageFont.truetype(_REG, int(H * 0.023))
        blocks.append(("detail", df, det, int(df.size * 1.55)))

    price_size = int(H * 0.088) if spec.get("price") else 0
    price_h = int(price_size * 1.44) if price_size else 0
    total = sum(b[-1] for b in blocks) + (price_h + int(H * 0.03) if price_h else 0)
    y = max(margin, (H - total) // 2 - int(H * 0.03))

    for kind, font, payload, adv in blocks:
        if kind == "eyebrow":
            _tracked(d, payload, font, margin, y, _hex(accent)[:3] + (255,), font.size * 0.34)
        elif kind == "headline":
            for line in payload:
                d.text((margin, y), line, font=font, fill=WHITE)
                y += int(font.size * 1.1)
            y += adv - int(len(payload) * font.size * 1.1)
            continue
        elif kind == "sub":
            for line in payload:
                d.text((margin, y), line, font=font, fill=SOFT)
                y += int(font.size * 1.35)
            y += adv - int(len(payload) * font.size * 1.35)
            continue
        else:
            r = max(2, int(H * 0.004))
            cyc = y + font.size * 0.5
            d.ellipse([margin, cyc - r, margin + r * 2, cyc + r], fill=_hex(accent))
            d.text((margin + r * 4, y), payload, font=font, fill=SOFT)
        y += adv

    if price_size:
        y += int(H * 0.03)
        _price_lockup(d, base, margin, y, spec.get("price", ""), _hex(accent), price_size)

    _store_footer(d, margin, H - margin - int(H * 0.026), spec.get("store_name", ""),
                  _hex(accent), int(H * 0.026), max_w=rail_w)


def _layout_band(base, d, spec, accent):
    """Frosted band across the bottom. The photo stays almost entirely visible."""
    W, H = base.size
    margin = int(W * 0.055)
    band_h = int(H * (0.30 if spec.get("subheadline") or spec.get("details") else 0.25))
    band_top = H - band_h
    _frost(base, (0, band_top, W, H), darken=138, blur=20)
    d.line([(0, band_top), (W, band_top)], fill=_hex(accent), width=max(3, H // 220))

    price_w = 0
    if spec.get("price"):
        pf_size = int(H * 0.072)
        tmp = ImageFont.truetype(_BOLD, pf_size)
        price_w = int(d.textlength(spec.get("price", ""), font=tmp) + pf_size * 0.72) + margin

    text_w = W - margin * 2 - price_w
    y = band_top + int(band_h * 0.16)

    if spec.get("eyebrow"):
        ef = ImageFont.truetype(_BOLD, int(H * 0.019))
        _tracked(d, spec.get("eyebrow", ""), ef, margin, y, _hex(accent)[:3] + (255,), ef.size * 0.34)
        y += int(ef.size * 2.0)

    hf, hlines, _ = _fit_block(d, spec.get("headline", "").upper(), _BOLD, text_w,
                               int(band_h * 0.46), int(H * 0.062), max_lines=2)
    for line in hlines:
        d.text((margin, y), line, font=hf, fill=WHITE)
        y += int(hf.size * 1.08)

    if spec.get("subheadline"):
        sf = ImageFont.truetype(_REG, int(H * 0.024))
        for line in _wrap(d, spec.get("subheadline", ""), sf, text_w, 1):
            d.text((margin, y + int(H * 0.006)), line, font=sf, fill=SOFT)
            y += int(sf.size * 1.3)

    if spec.get("details"):
        df = ImageFont.truetype(_REG, int(H * 0.021))
        text = "   ·   ".join(spec.get("details", [])[:3])
        d.text((margin, y + int(H * 0.008)),
               _wrap(d, text, df, text_w, 1)[0], font=df, fill=SOFT)

    if spec.get("price"):
        ps = int(H * 0.072)
        bw, bh = _price_lockup(d, base, W - margin, band_top + int(band_h * 0.30),
                               spec.get("price", ""), _hex(accent), ps, align="right")

    _store_footer(d, margin, band_top - int(H * 0.035), spec.get("store_name", ""),
                  _hex(accent), int(H * 0.024), max_w=int(W * 0.5))


def _layout_banner(base, d, spec, accent):
    """Frosted strip at the top, price medallion bottom-left. Good for wide art."""
    W, H = base.size
    margin = int(W * 0.045)
    strip_h = int(H * (0.26 if spec.get("subheadline") else 0.21))
    _frost(base, (0, 0, W, strip_h), darken=132, blur=18)
    d.line([(0, strip_h), (W, strip_h)], fill=_hex(accent), width=max(3, H // 220))

    y = int(strip_h * 0.16)
    if spec.get("eyebrow"):
        ef = ImageFont.truetype(_BOLD, int(H * 0.022))
        _tracked(d, spec.get("eyebrow", ""), ef, margin, y, _hex(accent)[:3] + (255,), ef.size * 0.34)
        y += int(ef.size * 2.0)

    hf, hlines, _ = _fit_block(d, spec.get("headline", "").upper(), _BOLD, W - margin * 2,
                               int(strip_h * 0.58), int(H * 0.070), max_lines=2)
    for line in hlines:
        d.text((margin, y), line, font=hf, fill=WHITE)
        y += int(hf.size * 1.08)

    # Subheadline and details both live in the top strip. An earlier version put
    # details in a bottom-right chip, where they collided with the store name.
    tail = []
    if spec.get("subheadline"):
        tail.append(spec.get("subheadline", ""))
    if spec.get("details"):
        tail.append("   ·   ".join(spec.get("details", [])[:3]))
    if tail:
        sf = ImageFont.truetype(_REG, int(H * 0.025))
        line = _wrap(d, "   ·   ".join(tail), sf, W - margin * 2, 1)[0]
        d.text((margin, y + int(H * 0.004)), line, font=sf, fill=SOFT)

    if spec.get("price"):
        ps = int(H * 0.086)
        _price_lockup(d, base, margin, H - margin - int(ps * 1.44),
                      spec.get("price", ""), _hex(accent), ps)

    _store_footer(d, W - margin, H - margin - int(H * 0.026), spec.get("store_name", ""),
                  _hex(accent), int(H * 0.026), align="right", max_w=int(W * 0.4))


_LAYOUT_FNS = {
    "poster": _layout_poster, "rail": _layout_rail,
    "band": _layout_band, "banner": _layout_banner,
}


def choose_layout(layout: str | None, width: int, height: int) -> str:
    """
    'auto' picks the treatment that suits the frame. POSTER is the default for
    square and portrait — it's the premium-spirits look the owner asked for:
    artwork-forward, big condensed headline, painted offer mark.
    """
    if layout in _LAYOUT_FNS:
        return layout
    if width > height * 1.15:
        return "banner"      # wide banner → top strip, headline needs the width
    return "poster"          # square + portrait → artwork-forward poster


def _render(background_png: bytes, spec: dict, layout: str | None = None) -> bytes:
    base = Image.open(BytesIO(background_png)).convert("RGBA")
    chosen = choose_layout(layout, *base.size)
    accent = spec.get("accent") or "#c1121f"

    overlay_base = base.copy()
    d = ImageDraw.Draw(overlay_base)
    _LAYOUT_FNS[chosen](overlay_base, d, spec, accent)

    buf = BytesIO()
    overlay_base.convert("RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()


async def render_ad_text(background_png: bytes, spec: dict, layout: str | None = None) -> bytes:
    """
    Typeset the deterministic ad text onto the AI scene.

    spec: {"eyebrow", "headline", "subheadline", "price", "store_name",
           "details": [...], "accent": "#rrggbb"} — design_plan.ad_text_spec().
    layout: rail | band | banner | auto/None.
    """
    logger.info("Ad text layer: layout=%s price=%s details=%d",
                layout or "auto", bool(spec.get("price")), len(spec.get("details") or []))
    return await asyncio.to_thread(_render, background_png, spec, layout)
