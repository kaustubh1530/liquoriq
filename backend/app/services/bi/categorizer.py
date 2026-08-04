"""
services/bi/categorizer.py — PHASE 22: CATEGORY INTELLIGENCE LAYER

The AdvEntPOS export has NO category column (verified: 100% null on the real
file), yet category is what makes "where is my cash sitting?" answerable. We
resolve it through a 5-tier cascade, first hit wins:

    TIER 1  MANUAL OVERRIDE     the owner's correction — absolute authority
    TIER 2  SKU CACHE           already resolved for this SKU on a past upload
    TIER 3  BRAND DICTIONARY    "TITO'S" → Vodka  (also yields the brand)
    TIER 4  CATEGORY DICTIONARY keywords, varietals, container formats
    TIER 5  AI FALLBACK         GPT picks from our FIXED list (elsewhere)
    else    "Other"             never a wild guess

ON RULE 4 OF THE BRIEF ("GPT never invents business logic"): classifying a
bottle as Wine is DATA ENRICHMENT, not business logic. No financial calculation
ever calls GPT. An AI-sourced category is labelled as such so the owner can
correct it, and a correction is promoted to Tier 1 permanently.

This module is PURE (no DB, no network) — tiers 1 and 2 are supplied by the
caller as plain dicts, and tier 5 is handled by the service layer. That keeps
the whole cascade unit-testable.
"""

import re

# The FIXED category list. GPT may only choose from this; it cannot invent one.
CATEGORIES = [
    "Whiskey", "Vodka", "Tequila", "Rum", "Gin", "Cognac/Brandy", "Liqueur",
    "Wine", "Champagne", "Beer", "Seltzer/RTD", "Sake/Soju", "Non-alcoholic",
    "Snacks", "Tobacco", "Non-product", "Other",
]

# Line items that are NOT merchandise: delivery fees, tips, card charges, bag
# tax. They sit in the sales export alongside real products and were quietly
# polluting the analytics — "TAX ITEM" turned up in the sold-out report as a
# product to reorder. Anything classified here is EXCLUDED from inventory
# metrics and opportunities, and its revenue is reported separately.
NON_PRODUCT = "Non-product"

SOURCE_CONFIDENCE = {
    "manual": "certain", "cache": "high", "brand": "high",
    "dictionary": "medium", "ai": "low", "fallback": "none",
}

# ── TIER 3: brand → (category, canonical brand name) ─────────────────────────
# Brand is the strongest signal available in a product name, and it also gives
# us the brand itself, which premium-upsell and bundle detection need.
_BRANDS: dict[str, tuple[str, str]] = {}


def _brand(names: str, category: str, canonical: str | None = None):
    for n in names.split("|"):
        _BRANDS[n] = (category, canonical or n.title())


# Whiskey / bourbon / scotch
_brand("JACK DANIEL|JIM BEAM|MAKERS MARK|MAKER'S|WOODFORD|BUFFALO TRACE|WELLER|"
       "BULLEIT|KNOB CREEK|BASIL HAYDEN|EAGLE RARE|ELIJAH CRAIG|FOUR ROSES|"
       "WILD TURKEY|EVAN WILLIAMS|OLD FORESTER|JAMESON|TULLAMORE|REDBREAST|"
       "GLENLIVET|GLENFIDDICH|MACALLAN|LAGAVULIN|LAPHROAIG|BALVENIE|CHIVAS|"
       "JOHNNIE WALKER|DEWAR|MONKEY SHOULDER|CROWN ROYAL|SEAGRAM|CANADIAN CLUB|"
       "FIREBALL|SKREWBALL|JEFFERSON|MICHTER|BLANTON|WHISTLEPIG|HIGH WEST|"
       "TRAVELLER|UNCLE NEAREST|ANGEL'S ENVY|GEORGE DICKEL|WHEATLEY", "Whiskey")
# Vodka
_brand("TITO|SMIRNOFF|ABSOLUT|GREY GOOSE|KETEL ONE|BELVEDERE|STOLICHNAYA|"
       "SVEDKA|NEW AMSTERDAM|PINNACLE|SKYY|CIROC|DEEP EDDY|THREE OLIVES|"
       "BURNETT|MCCORMICK|POPOV|GORDON'S VODKA|LUKSUSOWA", "Vodka")
# Tequila / mezcal
_brand("PATRON|DON JULIO|CASAMIGOS|JOSE CUERVO|ESPOLON|HORNITOS|MILAGRO|"
       "HERRADURA|CAZADORES|TEREMANA|CLASE AZUL|818 |CINCORO|EL JIMADOR|"
       "SAUZA|MONTELOBOS|DEL MAGUEY|MEZCAL", "Tequila")
# Rum
_brand("BACARDI|CAPTAIN MORGAN|MALIBU|KRAKEN|MOUNT GAY|APPLETON|MYERS|"
       "HAMILTON|GOSLING|PLANTATION|DIPLOMATICO|FLOR DE CANA|SAILOR JERRY|"
       "RONRICO|CRUZAN", "Rum")
# Gin
_brand("TANQUERAY|BOMBAY|HENDRICK|BEEFEATER|SEAGRAMS GIN|AVIATION|"
       "PLYMOUTH|MONKEY 47|ROKU|EMPRESS", "Gin")
# Cognac / brandy
_brand("HENNESSY|REMY MARTIN|COURVOISIER|MARTELL|D'USSE|E&J|CHRISTIAN BROTHERS|"
       "PAUL MASSON|ST REMY|COGNAC|ARMAGNAC", "Cognac/Brandy")
# Liqueur / aperitif / vermouth
_brand("BAILEY|KAHLUA|JAGERMEISTER|JAGER|APEROL|CAMPARI|COINTREAU|GRAND MARNIER|"
       "AMARETTO|DISARONNO|FIREBALL CINNAMON|ST GERMAIN|CHAMBORD|FRANGELICO|"
       "SAMBUCA|LICOR 43|RUMCHATA|SOUTHERN COMFORT|TRIPLE SEC|MARTINI & ROSSI|"
       "VERMOUTH|LILLET|PIMM|DRAMBUIE|GALLIANO|MIDORI|CHARTREUSE", "Liqueur")
# Seltzer / RTD
_brand("WHITE CLAW|TRULY|HIGH NOON|NUTRL|CUTWATER|ON THE ROCKS|SURFSIDE|"
       "BUD LIGHT SELTZER|VIZZY|BON V!V|TWISTED TEA|SMIRNOFF ICE|MIKE'S HARD|"
       "LOVERBOY|HAPPY THURSDAY", "Seltzer/RTD")
# Beer
_brand("BUDWEISER|BUD LIGHT|MILLER|COORS|CORONA|MODELO|PACIFICO|DOS EQUIS|"
       "HEINEKEN|STELLA|GUINNESS|MICHELOB|BUSCH|NATURAL LIGHT|NATTY|PBR|"
       "PABST|YUENGLING|SAM ADAMS|SIERRA NEVADA|BLUE MOON|LAGUNITAS|"
       "DOGFISH|FOUNDERS|BELL'S|GOOSE ISLAND|NEW BELGIUM|VOODOO RANGER|"
       "TECATE|VICTORIA|PERONI|ASAHI|SAPPORO|TSINGTAO|LANDSHARK|ROLLING ROCK|"
       "KEYSTONE|MILWAUKEE|OLD MILWAUKEE|GENESEE|LABATT|MOLSON", "Beer")
# Wine
_brand("BAREFOOT|YELLOW TAIL|JOSH CELLARS|APOTHIC|19 CRIMES|MENAGE A TROIS|"
       "KENDALL|ROBERT MONDAVI|BERINGER|SUTTER HOME|CUPCAKE|LA MARCA|"
       "SANTA MARGHERITA|CAYMUS|BONANZA|MEIOMI|DECOY|DUCKHORN|BOGLE|"
       "CHATEAU STE|LOUIS MARTINI|STELLA ROSA|RUFFINO|CAVIT|WOODBRIDGE|"
       "FRANZIA|CARLO ROSSI|ANDRE|COOK'S|KORBEL|MARTINI ASTI|RISATA|"
       "WHISPERING ANGEL|CH MONTAUD|CASTORANI|ARNALDO RIVERA", "Wine")
_brand("VEUVE CLICQUOT|MOET|DOM PERIGNON|PERRIER JOUET|TAITTINGER|BOLLINGER|"
       "LAURENT PERRIER|CHAMPAGNE", "Champagne")
# Non-alcoholic
_brand("COCA COLA|COKE|PEPSI|SPRITE|FANTA|DR PEPPER|MOUNTAIN DEW|CANADA DRY|"
       "SCHWEPPES|FEVER TREE|LA CROIX|PERRIER|SAN PELLEGRINO|TOPO CHICO|"
       "RED BULL|MONSTER|GATORADE|POWERADE|REAL LIME|REAL LEMON|ROSE'S|"
       "MARGARITA MIX|BLOODY MARY MIX|SIMPLY|MINUTE MAID|OCEAN SPRAY|"
       "DASANI|AQUAFINA|POLAND SPRING|ARIZONA|SNAPPLE|LIPTON", "Non-alcoholic")
# Tobacco / sundries
_brand("MARLBORO|CAMEL|NEWPORT|WINSTON|PALL MALL|AMERICAN SPIRIT|SWISHER|"
       "BLACK & MILD|BACKWOODS|GAME LEAF|WHITE OWL|DUTCH MASTERS|ZIG ZAG|"
       "JUUL|VUSE|ZYN|LIGHTER|ROLLING PAPER", "Tobacco")

# ── Second pass: brands found by auditing the 298 unresolved names on the
# real file. Each one was a genuine miss, not a guess.
_brand("EVERCLEAR|BUSHMILLS|ARDBEG|BOOKER|E.H. TAYLOR|EH TAYLOR|BENCHMARK|"
       "CANADIAN MIST|KENTUCKY GENTLEMAN|ZACKARIAH HARRIS|BOWMAN BROTHERS|"
       "BALCONES|OLE SMOKY|JACK DANILES", "Whiskey")
_brand("EFFEN|DELEON|LUKSUSOWA", "Vodka")
_brand("MONTEZUMA|CAMARENA|21 SEEDS|MAL BIEN|OCHO |ASTRAL|MARGARITAVILLE|"
       "TRES AGAVES|CAZCANES", "Tequila")
_brand("DON Q|BRUGAL|PLANTERAY|ENGLISH HARBOUR|REAL MCCOY|ANGOSTURA|"
       "AGUARDIENTE|ANTIOQUENO|CHACHO|OLD CARBINE|SAN ANTONIO GRANADA", "Rum")
_brand("CARAVELLA|PALLINI|RUSSO LIMONCELLO|LIMONCELLO|ST. GERMAIN|DOLIN|"
       "LUXARDO|GIFFARD|ITALICUS|SELECT PILLA|DON CICCIO|BONAL|NONINO|"
       "MOZART|MICHAELS CELTIC|MAD DOG|CAPRICCIO|HEUBLEIN|BOLS|CARPANO|"
       "99 SCHNPS|99 SCHPS|AMARO|FERNET|APERITIVO|ST. ELDER|ST ELDER", "Liqueur")
_brand("BUZZBALL|FOUR LOKO|BEAT BOX|TIP TOP|POST MERIDIEM|MONACO|VIBE |"
       "RECESS|YUZY|CLUBTAILS|LONG DRINK|CAYMAN JACK|MIKES|MIKE'S|"
       "JUST ADD ICE|RITA |LUCKY ONE|COASTAL GRAPE|XXL |SUNTORY|"
       "OH FRESH|SPINDRIFT|1800 ULTIMATE", "Seltzer/RTD")
_brand("KIRIN|AMSTEL|BLUEMOON|BLUE MOON|KONA|ALLAGASH|GOLDEN ROAD|UNIBROUE|"
       "SIXPOINT|ANXO|HEAVY SEAS|DC BRAU|GULDEN DRAAK|LAGUNITA|"
       "STELLA ARTOIS|MODELO ESPECIAL", "Beer")
_brand("EDNA VALLEY|LA CREMA|NOBILO|CLOUDY BAY|WHITEHAVEN|STARBOROUGH|"
       "PROPHECY|SAINT CLAIR|KIM CRAWFORD|OYSTER BAY|MATUA|BONTERRA|"
       "FRANCISCAN|MURPHY GOODE|JUGGERNAUT|GNARLY HEAD|BLACK BOX|BOTA BOX|"
       "JOEL GOTT|SPELL BOUND|BREAD & BUTTER|COPPOLA|LAPOSTOLLE|"
       "SANTA RITA|ESCUDO ROJO|ALLEGRINI|FRESCOBALDE|CARPINETO|TENUTA|"
       "COL D'ORCIA|IL POGGIONE|COLLOSORBO|RIDOLFI|BANFI|ROSCATO|"
       "MANISCHEWITZ|MONDAVI|RIUNITE|CHIARLI|LOLLI|THE POSSESSOR|"
       "BAROSSA|COUNT KAROLYI|SETTLEMENT|OCTOPODA|BLOCK 631|WOLFFER|"
       "BROADBENT|INNISKILLIN|KGM ICEWINE|ALCESTI|PIPON|90 CELLARS|"
       "HENRI BOURGEOIS|DOMAINE GIRAULT|LAUVERJAT|CLOS LE|MAS LA CHEVALIERE|"
       "PIEERE VIGNECOURT|SHABO|LIQUID LIGHT|CSM |GLORIA FERRER|"
       "LOUIS M. MARTINI|CIPRIANI", "Wine")
_brand("FREIXENET|CRISTALINO|LOUIS ROEDERER|LAMARCA", "Champagne")
_brand("SUIGEI|HAKUSHIKA|JINRO|IICHIKO|SHOCHU|SOJU", "Sake/Soju")
_brand("KETTLE|TRIDENT|SNICKERS|TURTLES|LEPOARD HONEY|FILTHY|"
       "SANTA BARBARA|5 HOUR ENERGY|5 HOUR ENEGRY", "Snacks")
_brand("EVERFRESH|MASTER OF MIX|STIRRINGS|SIMPLY LEMONADE", "Non-alcoholic")
_brand("RED CUP|PLASTIC CUPS|CORKSCREW|SOFT BAG", "Snacks")

# ── TIER 4: category dictionary — keywords, varietals, formats ───────────────
_KEYWORD_RULES: list[tuple[str, str]] = [
    # FIRST: strip out the things that aren't merchandise at all. These were
    # being scored as products — "TAX ITEM" appeared in the sold-out reorder
    # list — which is exactly the kind of quiet nonsense that destroys trust.
    ("Non-product", r"^(TAX ITEM|NON-TAX ITEM|TIP|DELIVERY CHARGE|"
                    r"CREDIT/DEBIT CARD TRAN FEE|DC BAG TAX)$|"
                    r"\b(DELIVERY FEE|SERVICE FEE|BAG TAX|BOTTLE DEPOSIT|"
                    r"GIFT CARD|STORE CREDIT|ROUNDING)\b|"
                    r"^(CITY HIVE|UBER)\s+(TIP|DELIVERY)"),
    ("Whiskey", r"\b(WHISK\w*|BOURBON|SCOTCH|\bRYE\b|SINGLE MALT|MOONSHINE)\b"),
    ("Vodka", r"\bVODKA\b"),
    ("Tequila", r"\b(TEQUILA|MEZCAL|ANEJO|A[NÑ]EJO|REPOSADO|BLANCO|SILVER TEQ)\b"),
    ("Rum", r"\b(RUM|CACHACA|RHUM)\b"),
    ("Gin", r"\bGIN\b"),
    ("Cognac/Brandy", r"\b(COGNAC|BRANDY|ARMAGNAC|PISCO|GRAPPA|\bVSOP\b|\bXO\b)\b"),
    ("Liqueur", r"\b(LIQUEUR|LIQUER|SCHNAPP\w*|APERITIF|VERMOUTH|BITTERS|"
                r"CREAM LIQUEUR|TRIPLE SEC|CURACAO|ABSINTHE|OUZO|SOJU|SAKE)\b"),
    ("Champagne", r"\b(CHAMPAGNE|PROSECCO|CAVA|SPUMANTE|ASTI|BRUT|SPARKLING)\b"),
    # Wine: shop staff abbreviate varietals heavily on the shelf tag, so the
    # abbreviations matter more than the full words. "SAUV BLANC" alone
    # accounted for dozens of misses on the real file.
    ("Wine", r"\b(WINE|CABERNET|CAB SAU\w*|SAUVIGNON|SAUV BL\w*|SAU BL\w*|"
             r"SAUV BLN|MERLOT|CHARDONNAY|CHARD\b|PINOT|P NOIR|P GRIGIO|"
             r"MOSCATO|RIESLING|MALBEC|ZINFANDEL|ZINFANDALE|SHIRAZ|SYRAH|"
             r"TEMPRANILLO|SANGIOVESE|CHIANTI|RIOJA|BAROLO|BRUNELLO|"
             r"MONTALCINO|BORDEAUX|BURGUNDY|SANCERRE|CHABLIS|VOUVRAY|"
             r"LAMBRUSCO|VINHO VERDE|GRUNER|VELTLINER|CARMENERE|ZIBIBBO|"
             r"ICEWINE|GSM\b|ROSE|ROSÉ|SANGRIA|PORT|SHERRY|MADEIRA|VINO|"
             r"BLEND|VARIETAL|RSV\b|RISERVA|RESERVA)\b"),
    ("Sake/Soju", r"\b(SAKE|SOJU|SHOCHU|JUNMAI|DAIGINJO|TOKUBETSU|MAKGEOLLI)\b"),
    ("Snacks", r"\b(CHIPS|GUM|CANDY|CHOCOLA\w*|NUTS|JERKY|OLIVES|CHERRIES|"
               r"PICKLE|HONEY|CUPS?|CORKSCREW|OPENER|GLASSWARE)\b"),
    ("Seltzer/RTD", r"\b(SELTZER|HARD SELTZER|\bRTD\b|CANNED COCKTAIL|"
                    r"READY TO DRINK|SPIKED)\b"),
    ("Beer", r"\b(BEER|LAGER|\bIPA\b|\bALE\b|PILSNER|STOUT|PORTER|CIDER|"
             r"HEFEWEIZEN|SAISON|MALT LIQUOR)\b"),
    ("Non-alcoholic", r"\b(SODA|JUICE|WATER|TONIC|MIXER|ENERGY DRINK|"
                      r"GINGER ALE|COLA|LEMONADE|ICED TEA|SYRUP|GRENADINE|"
                      r"BITTER LEMON|CLUB SODA|NA BEER|NON.?ALCOHOLIC)\b"),
    ("Tobacco", r"\b(CIGAR\w*|CIGARETTE|TOBACCO|VAPE|E.?LIQUID|HOOKAH|SHISHA|"
                r"PIPE|SNUFF|CHEW|POUCH)\b"),
]
_KEYWORD_RULES = [(c, re.compile(p, re.I)) for c, p in _KEYWORD_RULES]

# Container-format fallback. A 12-pack of 12oz cans is beer or seltzer far more
# often than anything else; a 2-litre bottle is soda. Weak but better than
# "Other", so it is deliberately the LAST rule and gets medium confidence.
_FORMAT_RULES = [
    ("Beer", re.compile(r"\d+\s*Oz.*\d+[- ]?PACK|(\b6|12|15|18|24|30)[- ]?PACK", re.I)),
    ("Non-alcoholic", re.compile(r"\b\d+(\.\d+)?\s*(LT|L|LITER)\b.*\b(SODA|COLA)\b|"
                                 r"\b(20|16|12)\s*Oz\b(?!.*PACK)", re.I)),
]

# ── Deterministic extraction from the name ───────────────────────────────────
_SIZE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(ML|L|LT|LITER|OZ|GAL)\b", re.I)
_PACK_RE = re.compile(r"(\d+)\s*[-–]?\s*(?:PACK|PK)\b", re.I)

_UNIT_TO_ML = {"ML": 1.0, "L": 1000.0, "LT": 1000.0, "LITER": 1000.0,
               "OZ": 29.5735, "GAL": 3785.41}


def extract_size(name: str) -> dict:
    """
    Size and pack from the product name. Present on 96% / 20% of the real file.
    Normalising to millilitres is what lets us compare 750ml against 1.75L of
    the same brand — the basis of premium-upsell detection.
    """
    out = {"size_text": None, "size_ml": None, "pack_count": None, "total_ml": None}

    if m := _SIZE_RE.search(name):
        value, unit = float(m.group(1)), m.group(2).upper()
        out["size_text"] = f"{m.group(1)} {unit.lower()}"
        out["size_ml"] = round(value * _UNIT_TO_ML.get(unit, 1.0), 2)

    if m := _PACK_RE.search(name):
        out["pack_count"] = int(m.group(1))

    if out["size_ml"]:
        out["total_ml"] = round(out["size_ml"] * (out["pack_count"] or 1), 2)
    return out


def _clean(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").upper()).strip()


def categorize(
    product_name: str,
    sku: str | None = None,
    overrides: dict | None = None,
    cache: dict | None = None,
) -> dict:
    """
    Resolve a product through the cascade.

    overrides / cache are plain dicts keyed by SKU (falling back to the cleaned
    name when a SKU is absent), supplied by the caller. Keeping I/O out here is
    what makes the whole cascade unit-testable.

    Returns: {category, brand, source, confidence, size_text, size_ml,
              pack_count, total_ml, needs_ai}
    """
    name = _clean(product_name)
    key = (sku or "").strip() or name
    size = extract_size(product_name or "")

    def result(category, brand, source):
        return {
            "category": category, "brand": brand, "source": source,
            "confidence": SOURCE_CONFIDENCE[source],
            "needs_ai": source == "fallback",
            **size,
        }

    # TIER 1 — the owner's correction always wins
    if overrides and key in overrides:
        entry = overrides[key]
        if isinstance(entry, dict):
            return result(entry.get("category", "Other"), entry.get("brand"), "manual")
        return result(entry, None, "manual")

    # TIER 2 — already resolved for this SKU on a previous upload
    if cache and key in cache:
        entry = cache[key]
        if isinstance(entry, dict):
            return result(entry.get("category", "Other"), entry.get("brand"), "cache")
        return result(entry, None, "cache")

    # TIER 3 — brand dictionary (longest match first, so "BUD LIGHT SELTZER"
    # beats "BUD LIGHT")
    for token in sorted(_BRANDS, key=len, reverse=True):
        if token in name:
            category, canonical = _BRANDS[token]
            return result(category, canonical, "brand")

    # TIER 4 — keyword / varietal dictionary, then container format
    for category, pattern in _KEYWORD_RULES:
        if pattern.search(name):
            return result(category, None, "dictionary")
    for category, pattern in _FORMAT_RULES:
        if pattern.search(name):
            return result(category, None, "dictionary")

    # TIER 5 is handled by the service layer (GPT); flag it and fall back.
    return result("Other", None, "fallback")


def categorize_many(rows, overrides=None, cache=None) -> list[dict]:
    """Categorise a list of {product_name, sku} dicts."""
    return [
        categorize(r.get("product_name", ""), r.get("sku"), overrides, cache)
        for r in rows
    ]


def coverage(results: list[dict]) -> dict:
    """How well the cascade did — surfaced in the UI so gaps are visible."""
    total = len(results) or 1
    by_source: dict[str, int] = {}
    for r in results:
        by_source[r["source"]] = by_source.get(r["source"], 0) + 1
    resolved = total - by_source.get("fallback", 0)
    return {
        "total": len(results),
        "resolved": resolved,
        "resolved_pct": round(resolved / total * 100, 1),
        "by_source": by_source,
        "needs_ai": by_source.get("fallback", 0),
    }
