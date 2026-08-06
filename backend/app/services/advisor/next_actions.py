"""
services/advisor/next_actions.py — PHASE 23.5: advice that connects to work.

Every answer ends with something the owner can click.

WHY THESE ARE DERIVED, NOT GENERATED

Asking the model to emit buttons means asking it to emit ROUTES, and a model
that invents `/clearance-wizard` produces a dead link — which reads as the
product being broken rather than the answer being wrong.

So the buttons come from what the advisor ACTUALLY LOOKED AT. If it pulled the
reorder list, "Open reorder list" is relevant by construction. The tools it
called are already recorded for the citation list; this reuses that same
observed signal for navigation.

Deterministic, so a link can never point somewhere that doesn't exist.
"""

# tool → the workflow that acts on what that tool told you.
# Ordered by how directly the workflow follows from the lookup.
BY_TOOL = {
    "reorder_list": [
        {"label": "Open reorder list", "route": "/inventory", "kind": "inventory"},
    ],
    "inventory_intelligence": [
        {"label": "Open inventory", "route": "/inventory", "kind": "inventory"},
        {"label": "Create shelf labels", "route": "/labels", "kind": "labels"},
    ],
    "category_intelligence": [
        {"label": "Business Intelligence", "route": "/intelligence", "kind": "analysis"},
        {"label": "Generate campaign", "route": "/ai", "kind": "campaign"},
    ],
    "action_center": [
        {"label": "Generate campaign", "route": "/ai", "kind": "campaign"},
        {"label": "Open inventory", "route": "/inventory", "kind": "inventory"},
    ],
    "customer_segments": [
        {"label": "View customers", "route": "/customers", "kind": "customers"},
        {"label": "Generate campaign", "route": "/ai", "kind": "campaign"},
    ],
    "campaign_performance": [
        {"label": "Generate campaign", "route": "/ai", "kind": "campaign"},
    ],
    "ai_strategies": [
        {"label": "Generate campaign", "route": "/ai", "kind": "campaign"},
        {"label": "Create ad", "route": "/creative", "kind": "ad"},
    ],
    "upcoming_holidays": [
        {"label": "Generate campaign", "route": "/ai", "kind": "campaign"},
        {"label": "Create ad", "route": "/creative", "kind": "ad"},
    ],
    "supplier_deals": [
        {"label": "Open inventory", "route": "/inventory", "kind": "inventory"},
    ],
    "revenue_trend": [
        {"label": "Business Intelligence", "route": "/intelligence", "kind": "analysis"},
    ],
    "product_lookup": [
        {"label": "Create shelf labels", "route": "/labels", "kind": "labels"},
        {"label": "Create ad", "route": "/creative", "kind": "ad"},
    ],
}

# When no tool ran — a short factual answer, or the model already knew enough.
DEFAULT = [
    {"label": "Generate campaign", "route": "/ai", "kind": "campaign"},
    {"label": "Open inventory", "route": "/inventory", "kind": "inventory"},
]

# Words in the answer that point at a workflow the tools alone wouldn't reveal.
# Only fires on an explicit recommendation, not on a passing mention.
BY_INTENT = [
    (("clearance", "discount", "mark down", "markdown"),
     {"label": "Launch clearance campaign", "route": "/ai?focus=clearance",
      "kind": "campaign"}),
    (("shelf talker", "shelf label", "price card", "tag the shelf"),
     {"label": "Create shelf labels", "route": "/labels", "kind": "labels"}),
    (("advertisement", "run an ad", "social post", "flyer"),
     {"label": "Create ad", "route": "/creative", "kind": "ad"}),
    (("text them", "win back", "win-back", "email them", "sms"),
     {"label": "View customers", "route": "/customers", "kind": "customers"}),
    (("upload", "weekly report", "daily transactions"),
     {"label": "Upload a report", "route": "/uploads", "kind": "upload"}),
]

MAX_ACTIONS = 3


def derive(tools_used: list[dict], answer: str = "",
           strategy_id: str | None = None) -> list[dict]:
    """
    The buttons to show under one answer, most relevant first, de-duplicated.

    Capped at three: a row of six buttons is a menu, and a menu is what the
    owner came here to avoid.

    `strategy_id` — when the advisor looked at a specific campaign, the Ad
    Creator link carries it, so the page opens ON that strategy rather than on
    whatever was selected last. A handoff that drops its subject is not a
    handoff; it is a menu item with extra steps.
    """
    picked: list[dict] = []
    seen: set[str] = set()

    def add(action):
        if action["route"] in seen:
            return
        seen.add(action["route"])
        picked.append(action)

    # Intent first — an explicit "run a clearance" is a stronger signal than
    # the fact that inventory was consulted along the way.
    lowered = (answer or "").lower()
    for phrases, action in BY_INTENT:
        if any(p in lowered for p in phrases):
            add(action)

    for used in tools_used or []:
        if not used.get("ok"):
            continue
        for action in BY_TOOL.get(used.get("tool"), []):
            add(action)

    if not picked:
        for action in DEFAULT:
            add(action)

    # Attach the strategy to anything that acts ON a strategy. Done here rather
    # than in the tables so every route that needs it gets it, including the
    # intent-derived ones.
    if strategy_id:
        picked = [
            {**a, "route": _with_strategy(a["route"], strategy_id)}
            if a["kind"] in STRATEGY_SCOPED else a
            for a in picked
        ]

    return picked[:MAX_ACTIONS]


# Workflows that operate on one campaign, and therefore need to know which.
STRATEGY_SCOPED = {"ad", "campaign"}


def _with_strategy(route: str, strategy_id: str) -> str:
    """Append ?strategy=<id>, preserving any query string already there."""
    if "strategy=" in route:
        return route
    separator = "&" if "?" in route else "?"
    return f"{route}{separator}strategy={strategy_id}"
