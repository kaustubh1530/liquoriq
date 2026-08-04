"""
services/bi/explain.py — PHASE 22: the AI EXPLANATION LAYER

This is the ONLY module in the BI engine that touches GPT, and it is
deliberately powerless: it receives finished numbers and returns prose.

THE CONTRACT
  · GPT is handed the deterministic result and told to EXPLAIN it.
  · GPT is explicitly forbidden from producing any figure that wasn't given.
  · Every number in the response is validated against the numbers we supplied;
    any invented figure means the explanation is DISCARDED and the deterministic
    template is used instead.
  · If OpenAI is down, out of credits, or slow, the engine loses nothing —
    the fallback text is written from the same numbers.

That last point is the test of whether "GPT only explains" is real: unplug it
and the product still tells the owner what to do.
"""

import logging
import re

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a retail business analyst explaining a finding to the
owner of an independent liquor store. You are given a finding that has ALREADY
been calculated from the store's own sales and stock data.

YOUR ONLY JOB IS TO EXPLAIN IT IN PLAIN, PROFESSIONAL BUSINESS ENGLISH.

ABSOLUTE RULES:
- NEVER invent, estimate, recalculate or adjust any number. You may only repeat
  figures that appear in the data you are given.
- NEVER contradict the finding or suggest the numbers might be different.
- If you want to mention a quantity you were not given, describe it in words
  instead ("a large share", "most of") — never make up a figure.
- Be concise and direct. No filler, no hype, no exclamation marks.
- Write for a busy shop owner, not an analyst. Short sentences.

Cover, in this order and with these exact JSON keys:
  why_it_exists    - one sentence on what in their data caused this
  why_it_matters   - one sentence on the business consequence
  expected_outcome - one sentence on what acting should achieve
  limitations      - one honest sentence on what this does NOT account for
  next_action      - one sentence naming the concrete next step

Respond with valid JSON only:
{"why_it_exists":"...","why_it_matters":"...","expected_outcome":"...",
 "limitations":"...","next_action":"..."}"""

REQUIRED_KEYS = ("why_it_exists", "why_it_matters", "expected_outcome",
                 "limitations", "next_action")

# Any run of digits with optional separators — used to police invented figures.
_NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _numbers_in(text: str) -> set[str]:
    """Normalised numeric tokens in a string, for comparison."""
    return {n.replace(",", "").rstrip(".0") or "0" for n in _NUMBER_RE.findall(str(text))}


def _allowed_numbers(action: dict) -> set[str]:
    """
    Every number we actually gave the model — including rounded forms, since
    "220660.61" is legitimately written as "220,661" or "220660" in prose.
    """
    allowed: set[str] = set()

    def add(value):
        try:
            number = float(value)
        except (TypeError, ValueError):
            return
        for variant in (number, round(number), int(number),
                        round(number, 1), round(number, 2)):
            allowed.add(str(variant).replace(",", "").rstrip(".0") or "0")

    def walk(node):
        if isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, (list, tuple)):
            for v in node:
                walk(v)
        elif isinstance(node, (int, float)):
            add(node)
        elif isinstance(node, str):
            for token in _NUMBER_RE.findall(node):
                add(token.replace(",", ""))

    walk(action)
    # Percentages and small integers are safe connective tissue ("one", "3 weeks")
    allowed.update(str(i) for i in range(0, 101))
    return allowed


def validate(explanation: dict, action: dict) -> tuple[bool, str]:
    """
    Reject an explanation that contains a figure we never supplied.

    This is the enforcement behind "GPT never calculates". Without it the rule
    is a hope; with it, a hallucinated number can't reach the owner.
    """
    if not isinstance(explanation, dict):
        return False, "not a JSON object"
    missing = [k for k in REQUIRED_KEYS if not explanation.get(k)]
    if missing:
        return False, f"missing fields: {missing}"

    allowed = _allowed_numbers(action)
    for key in REQUIRED_KEYS:
        for number in _numbers_in(explanation[key]):
            if number not in allowed:
                return False, f"invented number {number!r} in {key}"
    return True, ""


def fallback(action: dict) -> dict:
    """
    Deterministic prose from the same numbers. Used when OpenAI is unavailable
    OR when its answer failed validation. The product never depends on it.
    """
    evidence = action.get("evidence") or {}
    impact = action.get("business_impact_label") or ""
    kind = action.get("type", "")

    why = {
        "reorder": "Products that were selling have run out or are nearly out, "
                   "based on your stock levels and sales rate.",
        "clearance": "A large share of your stock is selling too slowly to clear "
                     "within a reasonable time, so the cash stays on the shelf.",
        "seasonal": "A holiday is approaching and you already hold stock in the "
                    "categories that sell around it.",
        "bundle": "Some products are moving quickly while others in the same "
                  "category are not.",
        "premium_upsell": "You stock the same brand at more than one price point, "
                          "and the cheaper option is selling.",
        "winback": "Customers who used to buy from you have not returned recently.",
        "campaign_repeat": "A campaign you ran previously produced measurable "
                           "extra sales.",
    }.get(kind, "This was identified from your sales and stock data.")

    return {
        "why_it_exists": why,
        "why_it_matters": f"The business impact is estimated at {impact}."
                          if impact else "This affects your cash position.",
        "expected_outcome": action.get("expected_outcome") or "",
        "limitations": _limitation_for(action),
        "next_action": action.get("suggested_action") or "",
        "source": "deterministic",
    }


def _limitation_for(action: dict) -> str:
    """Honest caveat, driven by the confidence we already computed."""
    confidence = action.get("confidence")
    reason = action.get("confidence_reason") or ""
    if confidence == "high":
        return f"Calculated from your own data ({reason})."
    if confidence == "medium":
        return f"Partly based on assumptions: {reason}."
    return (f"Treat as indicative only: {reason}. "
            "Your POS export contains no cost data, so profit is estimated.")


def _display_payload(action: dict) -> dict:
    """
    Exactly what the model is allowed to see: finished, already-computed display
    values. No sales rows, no stock counts, no prices — so there is no path by
    which it could recompute anything even if it tried.
    """
    return {
        "finding": action.get("title"),
        "business_impact": action.get("business_impact_label"),
        "expected_outcome": action.get("expected_outcome"),
        "confidence": action.get("confidence"),
        "confidence_reason": action.get("confidence_reason"),
        "evidence": action.get("evidence"),
        "suggested_action": action.get("suggested_action"),
    }


async def explain_action(action: dict, caller=None) -> dict:
    """
    Ask GPT to explain ONE finished action. Never raises: any failure — network,
    credits, bad JSON, or an invented number — returns the deterministic text.

    `caller` is injectable so tests can exercise this without the OpenAI SDK
    installed, and so the AI dependency stays at the edge rather than baked in.
    """
    if caller is None:
        from app.services.openai_service import generate_json_response as caller

    payload = _display_payload(action)

    try:
        raw = await caller(SYSTEM_PROMPT, _user_prompt(payload))
    except Exception as exc:  # noqa: BLE001 — any failure falls back, by design
        logger.warning("BI explanation unavailable, using deterministic text: %s", exc)
        return fallback(action)

    ok, reason = validate(raw, payload)
    if not ok:
        logger.warning("Discarded AI explanation (%s) for action=%s",
                       reason, action.get("type"))
        return fallback(action)

    return {**{k: raw[k] for k in REQUIRED_KEYS}, "source": "ai"}


def _user_prompt(payload: dict) -> str:
    import json
    return (
        "Explain this finding to the store owner. Use ONLY the numbers below; "
        "do not compute anything new.\n\n"
        + json.dumps(payload, indent=2, default=str)
    )


async def explain_actions(actions: list[dict], limit: int = 3, caller=None) -> list[dict]:
    """
    Explain the top N actions. Capped deliberately: the owner reads the first
    few, and every call costs money and latency for prose that is optional.
    """
    out = []
    for action in actions[:limit]:
        out.append({**action, "explanation": await explain_action(action, caller)})
    return out + [{**a, "explanation": fallback(a)} for a in actions[limit:]]
