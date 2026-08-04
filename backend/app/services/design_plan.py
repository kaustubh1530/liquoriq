"""
services/design_plan.py — MODULE 1: AI AD CREATOR (design plan + validation)

RESPONSIBILITY: turn a campaign strategy into a validated art-direction plan for
ONE professional advertisement. Nothing else. This module knows nothing about
labels, badges, or the Label Studio.

Instead of asking GPT for a freehand image prompt, we ask for a STRUCTURED design
plan (headline, subheadline, palette, composition, …). We then VALIDATE it
deterministically — length caps, forbidden internal-number scrub, no unsupported
factual claims — and COMPOSE the gpt-image-1 prompt from the validated plan.

WHAT THE AI RENDERS: background, product, lighting, composition. NO TEXT.
WHAT THE SERVER RENDERS: headline, exact price, store name (+ optionally a few
product details) — stamped with Pillow in ad_text_renderer.py so every character
is crisp, correctly spelled, and never cropped.
WHAT THE AI MUST NEVER RENDER: badges, stickers, ribbons, deal labels, discount
cards, coupons. Those belong to the Label Studio (module 2).

Pure functions (no DB / no network) → fully unit-tested.
"""

import re

# ── Limits (tunable) ──────────────────────────────────────────────────────────
HEADLINE_MAX = 34   # rendered by Pillow now, so it can be a little longer
SUBHEADLINE_MAX = 60
OFFER_MAX = 24
DETAIL_MAX_ITEMS = 3
DETAIL_ITEM_MAX = 40

INTERNAL = re.compile(r"\b(margin|markup|profit|cost|wholesale|COGS)\b", re.I)

HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

# The strategy's recommended_offer is a SENTENCE written for a human
# ("Lamarca Prosecco 750ml for $21.99 this weekend"). The ad needs the DEAL
# ITSELF, big. Pulling the token out is what stops the price slot from being
# filled with the product name all over again.
PRICE_TOKEN_RE = re.compile(
    r"(?P<money>\$\s?\d[\d,]*(?:\.\d{1,2})?)"
    r"|(?P<forprice>\b\d+\s*for\s*\$?\s?\d[\d,]*(?:\.\d{1,2})?)"
    r"|(?P<pct>\b\d{1,3}\s?%\s*off\b)"
    r"|(?P<bogo>\bBOGO\b|\bbuy\s*\d+\s*get\s*\d+(?:\s*free)?\b)",
    re.I,
)
DEFAULT_ACCENT = "#c1121f"

# Layouts the text renderer can typeset. "auto" lets the format decide.
AD_LAYOUTS = {"auto", "rail", "band", "banner"}

# Campaign types that justify showing customer-facing product details on the ad.
# Any other campaign stays CLEAN AND MINIMAL unless the owner explicitly opts in.
DETAIL_CAMPAIGN_TYPES = {
    "new_arrival", "product_spotlight", "premium_collection", "limited_edition",
}

CAMPAIGN_TYPES = {"standard", *DETAIL_CAMPAIGN_TYPES}

# Claim words that assert a verifiable product FACT. If the fact isn't confirmed
# in product_facts, the block mentioning it is dropped (no hallucinated proof /
# age / awards / origin / ingredients).
CLAIM_PATTERNS = {
    "proof":      re.compile(r"\b(\d+\s*proof|proof)\b", re.I),
    "abv":        re.compile(r"\b\d+(\.\d+)?\s*%?\s*(abv|alc)\b", re.I),
    "age":        re.compile(r"\b(\d+\s*(year|yr)s?\s*(old|aged)?|aged\s+\d+)\b", re.I),
    "award":      re.compile(r"\b(award|gold medal|double gold|best in|winner|rated \d+)\b", re.I),
    "origin":     re.compile(r"\b(from|made in|produced in|distilled in|hecho en)\b", re.I),
    "distilled":  re.compile(r"\b(\d+\s*times?\s*distilled|distilled\s*\d+\s*times?)\b", re.I),
    "ingredient": re.compile(r"\b(agave|blue agave|corn|rye|wheat|barley|grape|molasses)\b", re.I),
}


def show_product_details(campaign_type: str | None, owner_enabled: bool) -> bool:
    """
    Product details appear ONLY when the owner explicitly enables them, or when
    the campaign is one where facts genuinely sell the bottle (new arrival,
    spotlight, premium collection, limited edition). Otherwise: clean + minimal.
    """
    if owner_enabled:
        return True
    return (campaign_type or "standard").strip().lower() in DETAIL_CAMPAIGN_TYPES


def _scrub(text: str) -> str:
    """Remove any clause containing internal/owner-only terms."""
    if not text:
        return ""
    clauses = re.split(r"[()\[\]—;]|,(?=\s)", text)
    kept = [c.strip() for c in clauses if c.strip() and not INTERNAL.search(c)]
    return re.sub(r"\s{2,}", " ", ", ".join(kept)).strip(" -—,;")


def _cap(text: str, n: int) -> str:
    text = (text or "").strip()
    if len(text) <= n:
        return text
    return text[: n - 1].rstrip() + "…"


def extract_price(offer: str) -> str:
    """
    Pull the deal itself out of an offer sentence: "$21.99", "20% OFF", "BOGO",
    "2 for $30". Returns "" when the sentence contains no actual deal, in which
    case the caller falls back to showing a short offer phrase instead.
    """
    match = PRICE_TOKEN_RE.search(offer or "")
    if not match:
        return ""
    token = match.group(0).strip()
    token = re.sub(r"\s+", " ", token)
    token = re.sub(r"\$\s+", "$", token)
    return token.upper() if not token.startswith("$") else token


def is_amount(token: str) -> bool:
    """True for a plain money amount — those read naturally after the word 'AT'."""
    return bool(token) and token.startswith("$")


# An offer whose price is CONDITIONAL on buying something else. The price in
# these sentences belongs to a reward product, not to whatever bottle happens
# to be first in the promoted list.
CONDITIONAL_OFFER_RE = re.compile(
    r"\bbuy\s+\w+\s+.*\bget\b"          # "buy any 2 of the spirits, get X"
    r"|\bwith\s+(?:the\s+)?purchase\b"  # "with purchase of ..."
    r"|\bwhen\s+you\s+buy\b"
    r"|\bmix\s+and\s+match\b"
    r"|\bfree\b",
    re.I,
)


def is_conditional_offer(offer: str) -> bool:
    """
    True when the price only applies if the customer buys something else first.

    This matters because the ad shows ONE bottle with ONE price. Printing
    "AT $14.99" beside a bottle whose price is conditional states a price the
    store does not actually offer for that bottle on its own.
    """
    return bool(CONDITIONAL_OFFER_RE.search(offer or ""))


BUY_QTY_RE = re.compile(r"\bbuy\s+(?:any\s+)?(\d+)", re.I)


def condense_conditional(offer: str) -> str:
    """
    A short, TRUE line for a conditional deal.

    Suppressing the price entirely would leave the slot showing a chopped
    sentence ("Buy any 2 of the sele…"), which was the original complaint about
    these ads. "BUY 2, GET $14.99" fits, states the condition, and cannot be
    read as a flat price for the bottle on its own.
    """
    price = extract_price(offer)
    quantity = BUY_QTY_RE.search(offer or "")
    if quantity and price:
        return f"BUY {quantity.group(1)}, GET {price}"
    if quantity:
        return f"BUY {quantity.group(1)} & SAVE"
    if price:
        return f"{price} WITH PURCHASE"
    return ""


def _normalise(name: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", (name or "").lower())


def find_offer_subject(offer: str, products: list[str]) -> str | None:
    """
    Which promoted product the offer's price actually refers to.

    "Buy any 2 of the selected spirits, get Lamarca Prosecco for $14.99" prices
    the PROSECCO. Returning it lets the caller either make it the hero or
    suppress the price on a different hero — instead of stamping $14.99 onto
    Tito's, whose real shelf price is twice that.

    Matching is on the distinctive words of the product name (brand + varietal),
    ignoring sizes and units, so "Lamarca Prosecco 750ml" is found in a sentence
    that writes it as "Lamarca Prosecco".
    """
    haystack = _normalise(offer)
    if not haystack:
        return None

    best, best_score = None, 0
    for product in products or []:
        tokens = [t for t in _normalise(product).split()
                  if len(t) > 2 and not re.fullmatch(r"\d+|\d*(ml|l|oz|lt|pk|yr)", t)]
        # EVERY distinctive word must appear, and there must be at least two of
        # them. "Cab Sauv" is shared by two different wines in one campaign, so
        # a partial match would attribute a price to whichever was listed
        # first — the same class of error this function exists to prevent.
        # Failing to match is safe: the caller then suppresses the price.
        if len(tokens) < 2 or not all(t in haystack for t in tokens):
            continue
        if len(tokens) > best_score:
            best, best_score = product, len(tokens)
    return best


def price_is_plausible(price_token: str, known_unit_price: float | None,
                       floor_ratio: float = 0.5) -> bool:
    """
    Sanity-check an advertised price against what the POS says the product sells
    for. A promotion discounts a price; it does not divide it by three.

    Returns True when we have nothing to compare against — this guard exists to
    catch a price attributed to the WRONG PRODUCT, not to police genuine deals.
    """
    if not known_unit_price or known_unit_price <= 0:
        return True
    if not price_token or not price_token.startswith("$"):
        return True
    try:
        advertised = float(price_token.replace("$", "").replace(",", "").strip())
    except ValueError:
        return True
    if advertised <= 0:
        return False
    # Above shelf price is fine (multi-buy totals); far below means wrong product.
    return advertised >= known_unit_price * floor_ratio


def _accent(raw) -> str:
    """
    The AI picks an accent colour to match the scene it art-directed, so the
    typography belongs to THAT ad instead of every ad sharing one red. Anything
    that isn't a clean hex is rejected — this value is drawn, not eval'd, but a
    junk colour would crash Pillow.
    """
    value = str(raw or "").strip()
    if HEX_RE.match(value):
        if len(value) == 4:   # #abc → #aabbcc
            value = "#" + "".join(c * 2 for c in value[1:])
        return value.lower()
    return DEFAULT_ACCENT


def _facts_text(product_facts: dict | None) -> str:
    """Flatten confirmed facts to a lowercase blob to check claims against."""
    if not product_facts:
        return ""
    return " ".join(str(v) for v in product_facts.values() if v).lower()


def _claim_supported(text: str, facts_blob: str) -> bool:
    """A block asserting a fact is allowed ONLY if that fact appears in confirmed facts."""
    for pattern in CLAIM_PATTERNS.values():
        if pattern.search(text):
            if not facts_blob:
                return False
            tokens = [t for t in re.findall(r"[a-z0-9%]+", text.lower()) if len(t) > 2]
            if not any(t in facts_blob for t in tokens):
                return False
    return True


def validate_design_plan(
    plan: dict,
    hero_product: str,
    customer_offer: str,
    product_facts: dict | None = None,
    campaign_type: str | None = None,
    owner_wants_details: bool = False,
    promoted_products: list[str] | None = None,
    known_unit_price: float | None = None,
) -> dict:
    """
    Deterministically clean an AI design plan:
      - scrub internal numbers (margin/cost/profit/markup/wholesale) from EVERY field
      - enforce length caps on headline / subheadline / details
      - product details: only when gated ON; then ≤3, deduped, no hero-name repeat,
        and any unsupported factual claim is dropped
      - force the customer-facing offer (we control the exact price string)
    Returns a clean plan dict. Never raises.

    NOTE: badge_texts from the AI are DISCARDED on purpose — badges/stickers/
    ribbons are the Label Studio's job, not the ad generator's.
    """
    facts_blob = _facts_text(product_facts)
    out: dict = {}

    out["headline"] = _cap(_scrub(plan.get("headline", "")), HEADLINE_MAX)
    out["subheadline"] = _cap(_scrub(plan.get("subheadline", "")), SUBHEADLINE_MAX)
    if out["subheadline"] and not _claim_supported(out["subheadline"], facts_blob):
        out["subheadline"] = ""

    # Offer text is OWNER-controlled and already scrubbed upstream — trust it,
    # but pull out the actual DEAL so the price slot shows "$21.99" rather than
    # a truncated restatement of the product name.
    #
    # THE PRICE MUST BELONG TO THE BOTTLE ON THE AD. Previously the hero came
    # from products_to_promote[0] and the price from the offer sentence, with
    # nothing checking they referred to the same thing. On a real campaign that
    # printed "Tito's Handmade Vodka 1.75L — AT $14.99" when $14.99 was the
    # Prosecco's price in a buy-two-get-one offer and Tito's sells for $29.99.
    # An advertised price is a promise the store has to honour, so a price we
    # cannot attribute to the hero is not shown as a price at all.
    offer = (customer_offer or "").strip()
    price = extract_price(offer)
    conditional = is_conditional_offer(offer)

    if price:
        subject = find_offer_subject(offer, promoted_products or [])
        wrong_bottle = bool(
            subject and hero_product
            and _normalise(subject) != _normalise(hero_product)
        )
        if wrong_bottle or not price_is_plausible(price, known_unit_price):
            price = ""                              # can't attribute it — drop it
        elif conditional and is_amount(price):
            price = condense_conditional(offer)     # true, and states its condition

    out["offer_text"] = price or _cap(offer, OFFER_MAX)
    # "AT $14.99" is only ever printed for an unconditional amount.
    out["offer_is_amount"] = is_amount(out["offer_text"]) and not conditional

    # Product details — gated. When off, the ad stays clean and minimal.
    details: list[str] = []
    if show_product_details(campaign_type, owner_wants_details):
        seen = set()
        for raw in (plan.get("product_details") or plan.get("supporting_blocks") or []):
            b = _cap(_scrub(str(raw)), DETAIL_ITEM_MAX)
            key = b.lower()
            if not b or key in seen:
                continue
            if hero_product and hero_product.lower() in key:
                continue  # don't repeat the product name
            if not _claim_supported(b, facts_blob):
                continue
            seen.add(key)
            details.append(b)
            if len(details) >= DETAIL_MAX_ITEMS:
                break
    out["product_details"] = details

    # Art-direction fields (free text, scrubbed)
    for f in ["visual_theme", "palette", "typography_style", "product_placement",
              "background", "lighting", "composition"]:
        out[f] = _scrub(plan.get(f, ""))[:200]

    out["accent_color"] = _accent(plan.get("accent_color"))
    out["eyebrow"] = _cap(_scrub(plan.get("eyebrow", "")), 24).upper()
    out["hero_product"] = hero_product
    out["campaign_type"] = (campaign_type or "standard").strip().lower()
    return out


def compose_image_prompt(plan: dict, store_name: str = "") -> str:
    """
    Build the gpt-image-1 prompt from a VALIDATED plan.

    The AI renders ONLY: attractive background, correct product, premium lighting,
    professional composition. NO text of any kind, and explicitly NO badges,
    stickers, ribbons, price tags, or coupon graphics — the server stamps the
    headline/price/store name, and the Label Studio owns every badge.

    store_name is accepted (and deliberately unused in the prompt) so callers keep
    a stable signature; the store name is rendered by Pillow, never by the model.
    """
    hero = plan.get("hero_product") or "the promoted bottle"
    parts = [
        "Design the BACKGROUND ARTWORK for a premium liquor-store advertisement — "
        "the quality of a paid agency campaign photograph.",
        f"HERO PRODUCT: {hero} — the single clear focal point, sharply lit, placed "
        "on the RIGHT side of the frame with generous breathing room. Do NOT add "
        "other or unrelated liquor brands, and no clutter of random bottles.",
        f"VISUAL THEME: {plan.get('visual_theme','')}.",
        f"BACKGROUND: {plan.get('background','')} — make it RICH, ATTRACTIVE and "
        "ATMOSPHERIC: a beautifully styled, immersive themed scene with real depth, "
        "texture, tasteful props, and mood. Eye-catching and premium — just slightly "
        "softer/blurred behind the product so the bottle stays the hero. "
        "NOT a plain or empty background.",
        f"LIGHTING: {plan.get('lighting','')} — cinematic, dimensional lighting with "
        "highlights and shadows for a polished, high-end look.",
        f"COMPOSITION: {plan.get('composition','')}. Strong visual hierarchy, one "
        "clear focal point, rich but never cluttered. Keep the LEFT THIRD of the "
        "frame visually calm and uncluttered (darker or softly blurred) — a caption "
        "will be placed there afterwards.",
        f"COLOR PALETTE: {plan.get('palette','')} — a bold, cohesive palette matched "
        "to the theme.",
        "ABSOLUTELY NO TEXT: render no words, letters, numbers, prices, headlines, "
        "logos, or store names anywhere in the image.",
        "ABSOLUTELY NO GRAPHIC OVERLAYS: no badges, stickers, ribbons, banners, "
        "seals, starbursts, price tags, discount cards, coupons, or sale labels. "
        "Just the photographic scene and the product.",
        "Adults 25+ only; classy; never depict excessive drinking.",
    ]
    return "\n".join(p for p in parts if p)


def ad_text_spec(plan: dict, store_name: str) -> dict:
    """
    The deterministic text the SERVER will stamp onto the AI scene.

    This is the hand-off between "the AI made a picture" and "we made an ad".
    Every string here is owner-controlled or validated — never model-generated
    pixels, so the price is always exactly what the owner typed.
    """
    return {
        "eyebrow": plan.get("eyebrow", ""),
        "headline": plan.get("headline", ""),
        "subheadline": plan.get("subheadline", ""),
        "price": plan.get("offer_text", ""),
        "price_is_amount": bool(plan.get("offer_is_amount")),
        "product": plan.get("hero_product", ""),
        "store_name": store_name,
        "details": list(plan.get("product_details") or []),
        "accent": plan.get("accent_color", DEFAULT_ACCENT),
    }
