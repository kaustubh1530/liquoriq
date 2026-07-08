"""
services/compose_service.py — Price-overlay ad composition (Phase 11)

Takes the AI-generated background + the owner's confirmed prices and produces
the FINAL postable ad. All text is drawn by Pillow, not the image model —
deterministic, pixel-perfect, no AI typos, no fake labels, always the exact
price the owner typed.

Layout (1024×1024):
  ┌──────────────────────────────┐
  │   AI background image        │
  │                              │
  │ ╭──────────────────────────╮ │
  │ │ HEADLINE (max 2 lines)   │ │  ← semi-transparent dark panel,
  │ │ Product name …    $12.99 │ │    white text, amber prices
  │ │ Product name …     $8.49 │ │
  │ │ ─ store name footer ─    │ │
  │ ╰──────────────────────────╯ │
  └──────────────────────────────┘

Fonts are bundled in app/assets/fonts (DejaVu — free license) because the
deploy container has no system fonts guaranteed.
"""

import asyncio
import logging
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

_FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
_FONT_BOLD = str(_FONT_DIR / "DejaVuSans-Bold.ttf")
_FONT_REG = str(_FONT_DIR / "DejaVuSans.ttf")

# ── Layout constants ───────────────────────────────────────────────────────────
MARGIN = 48            # panel distance from image edges
PAD = 40               # inner panel padding
HEADLINE_SIZE = 52
ROW_SIZE = 36
PRICE_SIZE = 38
FOOTER_SIZE = 24
ROW_GAP = 18
PANEL_FILL = (12, 10, 8, 200)      # near-black, ~78% opaque
TEXT_WHITE = (255, 255, 255, 255)
PRICE_AMBER = (250, 190, 88, 255)  # warm gold — pops on dark panel
FOOTER_GREY = (200, 195, 188, 255)
MAX_ROWS = 5


def _fmt_price(price: float) -> str:
    return f"${price:,.2f}"


def _wrap_headline(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    """Greedy word-wrap, capped at 2 lines (ellipsis if it still overflows)."""
    words, lines, current = text.split(), [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
            if len(lines) == 2:
                break
    if current and len(lines) < 2:
        lines.append(current)
    if len(lines) == 2 and draw.textlength(lines[1], font=font) > max_width:
        while lines[1] and draw.textlength(lines[1] + "…", font=font) > max_width:
            lines[1] = lines[1][:-1]
        lines[1] += "…"
    return lines


def _truncate(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> str:
    if draw.textlength(text, font=font) <= max_width:
        return text
    while text and draw.textlength(text + "…", font=font) > max_width:
        text = text[:-1]
    return text + "…"


def _render(background_png: bytes, headline: str, items: list[dict], store_name: str) -> bytes:
    """Synchronous Pillow work — run via asyncio.to_thread from the async wrapper."""
    base = Image.open(BytesIO(background_png)).convert("RGBA")
    W, H = base.size

    headline_font = ImageFont.truetype(_FONT_BOLD, HEADLINE_SIZE)
    row_font = ImageFont.truetype(_FONT_REG, ROW_SIZE)
    price_font = ImageFont.truetype(_FONT_BOLD, PRICE_SIZE)
    footer_font = ImageFont.truetype(_FONT_REG, FOOTER_SIZE)

    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    panel_w = W - 2 * MARGIN
    inner_w = panel_w - 2 * PAD
    rows = items[:MAX_ROWS]

    # ── Measure panel height ──
    head_lines = _wrap_headline(draw, headline.upper(), headline_font, inner_w)
    head_h = len(head_lines) * (HEADLINE_SIZE + 8)
    rows_h = len(rows) * (ROW_SIZE + ROW_GAP)
    footer_h = FOOTER_SIZE + 14
    panel_h = PAD + head_h + 20 + rows_h + footer_h + PAD

    x0, y0 = MARGIN, H - MARGIN - panel_h
    draw.rounded_rectangle([x0, y0, x0 + panel_w, y0 + panel_h], radius=28, fill=PANEL_FILL)

    # ── Headline ──
    y = y0 + PAD
    for line in head_lines:
        draw.text((x0 + PAD, y), line, font=headline_font, fill=TEXT_WHITE)
        y += HEADLINE_SIZE + 8
    y += 20

    # ── Price rows: name left, price right, dotted leader between ──
    for item in rows:
        price_text = _fmt_price(float(item["price"]))
        price_w = draw.textlength(price_text, font=price_font)
        name_max = inner_w - price_w - 30
        name = _truncate(draw, str(item["product_name"]), row_font, name_max)
        draw.text((x0 + PAD, y), name, font=row_font, fill=TEXT_WHITE)
        draw.text((x0 + PAD + inner_w - price_w, y - 2), price_text, font=price_font, fill=PRICE_AMBER)
        y += ROW_SIZE + ROW_GAP

    # ── Footer: store name ──
    footer = store_name
    footer_w = draw.textlength(footer, font=footer_font)
    draw.text((x0 + PAD + (inner_w - footer_w) / 2, y + 6), footer, font=footer_font, fill=FOOTER_GREY)

    # ── Composite + encode ──
    final = Image.alpha_composite(base, overlay).convert("RGB")
    buf = BytesIO()
    final.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


async def render_final_ad(
    background_png: bytes,
    headline: str,
    items: list[dict],
    store_name: str,
) -> bytes:
    """
    Async wrapper: Pillow is synchronous/CPU-bound, so we run it in a thread
    to keep the event loop free (same pattern as the Cloudinary upload).

    items: [{"product_name": str, "price": float}], max 5 rendered.
    """
    logger.info("Composing final ad: %d price rows", len(items))
    return await asyncio.to_thread(_render, background_png, headline, items, store_name)
