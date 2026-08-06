"""
services/campaign_context.py — PHASE 23.6: one campaign, understood once.

THE PROBLEM

The owner asks the advisor what campaign to run. The advisor answers. He clicks
"Create ad" — and the Ad Creator asks him to describe the campaign again:
what's the offer, what type is it, what should it look like. Everything he is
being asked, the system already knows.

THE SHAPE OF THE FIX

Not "make the Ad Creator smarter". One CAMPAIGN CONTEXT, derived once from a
strategy, that every downstream tool reads. The Ad Creator is the first
consumer; Label Studio, the scheduler, social posting, SMS and email are the
next ones, and none of them will re-derive any of this.

If each page inferred its own campaign type, the ad would eventually say
"Premium Collection" while the shelf label said "Standard" for the same
campaign — the Phase 22 lesson about two sources of truth, in a new costume.

TWO RULES

1. EVERY INFERENCE LANDS ON A REAL VALUE. campaign_type must be one of the
   five the backend accepts; layout one of the four the renderer can typeset.
   Inference that produces a value the system rejects is worse than no
   inference, because the failure is silent and arrives at generation time.

2. NOTHING IS INVENTED. Product facts come from what the owner has already
   confirmed. The look-and-feel is composed from the strategy's own occasion
   and products. No GPT call — this is reading and mapping, and a model call
   here would add latency to a page that should feel instant.
"""

import logging
import re
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# ── Vocabularies. These MUST match what the backend accepts. ─────────────────
# design_plan.CAMPAIGN_TYPES and design_plan.AD_LAYOUTS are the authority; a
# value outside them is rejected at generation, long after the owner stopped
# looking at this screen.

CAMPAIGN_TYPE_RULES = [
    # (keywords in occasion/title/type, campaign_type, why)
    (("new arrival", "new product", "just landed", "launch", "just in"),
     "new_arrival", "the strategy is about something new to the shelf"),
    (("limited", "allocated", "rare", "single barrel", "one-off"),
     "limited_edition", "the strategy names limited or allocated stock"),
    (("premium", "luxury", "top shelf", "reserve", "gift", "christmas",
      "diwali", "father"),
     "premium_collection", "this is a premium or gifting occasion"),
    (("tasting", "spotlight", "featured", "staff pick"),
     "product_spotlight", "the strategy features a specific product"),
]
DEFAULT_CAMPAIGN_TYPE = ("standard", "a general promotion")

LAYOUT_RULES = [
    (("premium", "luxury", "reserve", "gift", "christmas", "whisky", "whiskey",
      "scotch", "cognac"),
     "rail", "premium products read better with a vertical text rail beside "
             "the bottle"),
    (("beer", "seltzer", "case", "party", "super bowl", "bbq", "cookout",
      "labor day", "july 4"),
     "band", "volume promotions need the price loud along the bottom"),
    (("sale", "clearance", "discount", "blowout", "% off"),
     "banner", "a price-led promotion leads with a top banner"),
]
DEFAULT_LAYOUT = ("auto", "let the renderer choose from the copy length")

FORMAT_RULES = [
    (("flyer", "poster", "print", "in-store", "window"),
     "portrait", "print and window material is portrait"),
    (("facebook cover", "banner", "website", "header"),
     "landscape", "web banners and covers are landscape"),
]
DEFAULT_FORMAT = ("square", "square posts fit Instagram and Facebook feeds")

# Scene direction per occasion. Composed rather than generated: a model call
# here would add two seconds to a page that should already be filled in.
SCENE_BY_OCCASION = {
    "labor day": "Outdoor summer barbecue in golden late-afternoon light, "
                 "cooler of iced bottles, string lights, relaxed holiday mood.",
    "memorial day": "Backyard cookout at the start of summer, bright daylight, "
                    "ice bucket, casual and warm.",
    "july 4": "Summer evening celebration, warm light, patriotic bunting kept "
              "subtle, bottles on ice.",
    "independence day": "Summer evening celebration, warm light, subtle "
                        "patriotic accents, bottles on ice.",
    "super bowl": "Game-day spread on a table, snacks and cases, warm indoor "
                  "lighting, energetic.",
    "cinco de mayo": "Bright festive setting with limes and salt, warm colours, "
                     "sunlit patio.",
    "st. patrick": "Warm pub interior, dark wood, green accents kept tasteful.",
    "thanksgiving": "Set dinner table in warm autumn light, candles, family "
                    "hosting atmosphere.",
    "christmas": "Warm fireplace and elegant holiday lighting, premium gift "
                 "bottles, deep reds and golds.",
    "new year": "Elegant midnight celebration, sparkling wine, dark background "
                "with gold light, upmarket.",
    "valentine": "Intimate candlelit setting, soft warm light, romantic and "
                 "restrained.",
    "halloween": "Moody evening scene with warm amber lighting, tasteful, not "
                 "cartoonish.",
    "oktoberfest": "Autumn beer-hall setting, warm wood, amber light.",
    "father": "Handsome study or workshop setting, leather and wood, warm "
              "masculine light.",
}

SCENE_BY_CATEGORY = {
    "whiskey": "Luxury lounge with dark wood, leather and low warm lighting.",
    "tequila": "Sunlit patio setting with limes and agave, bright and fresh.",
    "wine": "Elegant vineyard table at golden hour, linen and glassware.",
    "champagne": "Upmarket celebration setting, dark background with gold light.",
    "beer": "Casual outdoor setting with an iced cooler, bright daylight.",
    "seltzer/rtd": "Bright poolside or beach setting, cold cans, summer light.",
    "vodka": "Clean modern bar setting, cool light, crisp and minimal.",
    "gin": "Botanical setting with citrus and herbs, bright and fresh.",
    "rum": "Warm tropical setting, golden light, relaxed.",
    "cognac/brandy": "Warm study with leather and amber light, premium.",
    "liqueur": "Cosy interior with warm light and rich colour.",
}


def _haystack(strategy) -> str:
    """Everything the strategy says about itself, lowercased, in one string."""
    parts = [
        getattr(strategy, "strategy_title", "") or "",
        getattr(strategy, "occasion", "") or "",
        getattr(strategy, "strategy_type", "") or "",
        getattr(strategy, "recommended_offer", "") or "",
        getattr(strategy, "reason", "") or "",
        " ".join(getattr(strategy, "products_to_promote", None) or []),
    ]
    return " ".join(parts).lower()


def _first_match(rules, haystack, default):
    for keywords, value, why in rules:
        if any(k in haystack for k in keywords):
            return value, why
    return default


def _scene(strategy, category: str | None, haystack: str) -> tuple[str, str]:
    """
    Art direction, composed from what the strategy already says.

    Occasion beats category: a Christmas whiskey ad should look like Christmas,
    not like every other whiskey ad.
    """
    for occasion, scene in SCENE_BY_OCCASION.items():
        if occasion in haystack:
            return scene, f"the strategy is built around {occasion.title()}"

    if category:
        scene = SCENE_BY_CATEGORY.get(category.lower())
        if scene:
            return scene, f"{category} products photograph well in this setting"

    return "", ""


_AMOUNT = r"\$\s?\d[\d,]*(?:\.\d{1,2})?"

# "at $14.99", "for $21.99", "only $9.99", "now $30" — the words that precede a
# SELLING price rather than a discount.
_PRICED_AT = re.compile(rf"\b(?:at|for|only|now|just)\s+({_AMOUNT})", re.I)


def extract_price(offer: str) -> str:
    """
    The SELLING price from an offer sentence.

    Naively taking the first dollar amount is wrong, and wrong in the expensive
    direction: "Buy any 2 cases, save $10 — Modelo 12pk at $14.99" would yield
    $10, and the ad would advertise a twelve-pack for the value of its own
    discount. Same failure as the Phase 22 hero-price bug, in a new place.

    So: prefer an amount introduced by "at/for/only/now", and otherwise take the
    LAST amount, since savings and thresholds are stated before the price.
    """
    text = offer or ""
    priced = _PRICED_AT.search(text)
    if priced:
        return priced.group(1).replace(" ", "")

    amounts = re.findall(_AMOUNT, text)
    return amounts[-1].replace(" ", "") if amounts else ""


async def build(strategy, store_id: uuid.UUID, db: AsyncSession) -> dict:
    """
    Everything a downstream tool needs to act on this campaign.

    Each inferred field carries WHY it was chosen, so the UI can show the owner
    that the form was filled from his strategy rather than guessed at — and so
    he knows what to change if it guessed wrong.
    """
    haystack = _haystack(strategy)
    products = list(getattr(strategy, "products_to_promote", None) or [])
    hero = products[0] if products else ""

    # Confirmed facts and the library photo — never invented, only recalled.
    facts, category, photo_url = {}, None, None
    if hero:
        try:
            from app.services.product_facts_service import get_facts
            stored = await get_facts(store_id, hero, db)
            if stored:
                facts = stored.get("facts") or {}
                category = stored.get("category")
        except Exception:  # noqa: BLE001 — optional enrichment, never fatal
            logger.warning("Could not load product facts for %s", hero, exc_info=True)
        try:
            from app.services.product_photo_service import get_photo_url
            photo_url = await get_photo_url(store_id, hero, db)
        except Exception:  # noqa: BLE001
            logger.warning("Could not load product photo for %s", hero, exc_info=True)

    campaign_type, type_why = _first_match(CAMPAIGN_TYPE_RULES, haystack,
                                           DEFAULT_CAMPAIGN_TYPE)
    layout, layout_why = _first_match(LAYOUT_RULES, haystack, DEFAULT_LAYOUT)
    image_format, format_why = _first_match(FORMAT_RULES, haystack, DEFAULT_FORMAT)
    scene, scene_why = _scene(strategy, category, haystack)

    offer = getattr(strategy, "recommended_offer", "") or ""

    return {
        "strategy_id": str(strategy.id),

        # What the owner reads before pressing Generate.
        "summary": {
            "campaign": getattr(strategy, "strategy_title", "") or "",
            "goal": getattr(strategy, "reason", "") or "",
            "occasion": getattr(strategy, "occasion", "") or "",
            "audience": getattr(strategy, "target_customer_segment", "") or "",
            "offer": offer,
            "primary_product": hero,
            "expected_outcome": getattr(strategy, "expected_impact", "") or "",
            "products": products,
        },

        # What the form is filled with. Each with its reason.
        "prefill": {
            "offer": offer,
            "price": extract_price(offer),
            "campaign_type": campaign_type,
            "layout": layout,
            "image_format": image_format,
            "instructions": scene,
            "product_url": photo_url or "",
            "category": category or "",
            "facts": facts,
            # Product details are switched on only when the campaign type is
            # one that justifies them AND we actually have facts to show. An
            # empty details panel is worse than none.
            "show_details": bool(facts) and campaign_type != "standard",
        },

        "reasons": {
            "campaign_type": type_why,
            "layout": layout_why,
            "image_format": format_why,
            "instructions": scene_why,
            "offer": "taken from the offer in your strategy" if offer else "",
            "product_url": "your saved photo for this product" if photo_url else "",
            "facts": "product details you confirmed earlier" if facts else "",
        },

        "source": "ai_strategy",
    }
