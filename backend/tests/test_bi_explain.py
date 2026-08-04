"""
tests/test_bi_explain.py — PHASE 22: the AI explanation layer

The brief's hardest rule is "GPT must NEVER calculate business numbers". A
prompt asking nicely is a hope, not a guarantee. These tests cover the
ENFORCEMENT: every figure in an AI response is checked against the figures we
supplied, and anything invented causes the whole explanation to be discarded in
favour of deterministic text.

The other thing under test: unplug OpenAI and the product still works.
"""

import pytest

from app.services.bi import explain as E

ACTION = {
    "type": "clearance",
    "title": "$220,661 is frozen in 466 slow-moving products",
    "business_impact_label": "$132,396",
    "expected_outcome": "Free up roughly $132,396 in cash at a 60% clearance rate",
    "confidence": "high",
    "confidence_reason": "measured directly from your own stock levels",
    "evidence": {"cash_frozen": 220660.61, "products": 466,
                 "sleeping_over_a_year": 202, "recovery_rate": 0.6},
    "suggested_action": "Run a clearance campaign on the highest-value slow movers",
}

GOOD = {
    "why_it_exists": "466 products are selling too slowly to clear.",
    "why_it_matters": "That leaves $220,661 tied up in stock.",
    "expected_outcome": "Clearing them should free about $132,396.",
    "limitations": "Your export has no cost data, so profit is estimated.",
    "next_action": "Start a clearance on the highest-value items.",
}


# ── The enforcement ──────────────────────────────────────────────────────────

def test_a_faithful_explanation_is_accepted():
    ok, reason = E.validate(GOOD, ACTION)
    assert ok, reason


def test_an_invented_number_is_rejected():
    """The core guarantee. A figure we never supplied must never reach the owner."""
    bad = {**GOOD, "why_it_matters": "You are losing $87,500 every single month."}
    ok, reason = E.validate(bad, ACTION)
    assert not ok
    assert "invented number" in reason


@pytest.mark.parametrize("field", list(E.REQUIRED_KEYS))
def test_invented_numbers_are_caught_in_every_field(field):
    bad = {**GOOD, field: "This is worth $999,111 to you."}
    ok, _ = E.validate(bad, ACTION)
    assert not ok


def test_rounded_forms_of_supplied_numbers_are_allowed():
    """220660.61 is legitimately written as '220,661' in prose — don't reject that."""
    ok, reason = E.validate(
        {**GOOD, "why_it_matters": "About $220,661 is tied up across 466 products."},
        ACTION)
    assert ok, reason


def test_percentages_and_small_integers_are_allowed():
    """Connective tissue like '3 weeks' or '60%' must not trip the guard."""
    ok, reason = E.validate(
        {**GOOD, "next_action": "Discount by 30% over the next 4 weeks."}, ACTION)
    assert ok, reason


def test_missing_fields_are_rejected():
    ok, reason = E.validate({"why_it_exists": "Only one field"}, ACTION)
    assert not ok and "missing" in reason


def test_non_dict_response_is_rejected():
    for junk in (None, "a string", [1, 2, 3]):
        ok, _ = E.validate(junk, ACTION)
        assert not ok


# ── The fallback: the product survives without OpenAI ────────────────────────

def test_fallback_produces_every_required_field():
    out = E.fallback(ACTION)
    for key in E.REQUIRED_KEYS:
        assert out[key], key
    assert out["source"] == "deterministic"


def test_fallback_only_repeats_numbers_we_already_had():
    """The fallback is itself held to the rule it enforces."""
    ok, reason = E.validate(E.fallback(ACTION), ACTION)
    assert ok, reason


@pytest.mark.parametrize("kind", ["reorder", "clearance", "seasonal", "bundle",
                                  "premium_upsell", "winback", "campaign_repeat"])
def test_fallback_has_wording_for_every_opportunity_type(kind):
    out = E.fallback({**ACTION, "type": kind})
    assert len(out["why_it_exists"]) > 20


def test_fallback_limitation_reflects_confidence():
    low = E.fallback({**ACTION, "confidence": "low", "confidence_reason": "an assumption"})
    high = E.fallback({**ACTION, "confidence": "high", "confidence_reason": "measured"})
    assert "indicative" in low["limitations"]
    assert "your own data" in high["limitations"].lower()


def _explain(fake):
    """
    Run explain_action with an injected caller. No OpenAI SDK needed, and the
    same loop style as the rest of the suite (asyncio.run() would close the
    shared event loop and break the SMS tests).
    """
    import asyncio
    return asyncio.get_event_loop().run_until_complete(E.explain_action(ACTION, fake))


def test_openai_failure_falls_back_silently():
    """Out of credits, network down — the owner still gets their explanation."""
    async def boom(*_a, **_k):
        raise RuntimeError("out of credits")
    out = _explain(boom)
    assert out["source"] == "deterministic"
    assert out["next_action"]


def test_hallucinated_ai_response_is_replaced_by_the_fallback():
    async def liar(*_a, **_k):
        return {**GOOD, "why_it_matters": "You lose $4,321,000 a year."}
    out = _explain(liar)
    assert out["source"] == "deterministic"
    assert "4,321,000" not in str(out)


def test_good_ai_response_is_used():
    async def honest(*_a, **_k):
        return GOOD
    out = _explain(honest)
    assert out["source"] == "ai"
    assert out["why_it_exists"] == GOOD["why_it_exists"]


# ── What the model is allowed to see ─────────────────────────────────────────

def test_the_prompt_forbids_calculation_explicitly():
    flat = " ".join(E.SYSTEM_PROMPT.split())   # the prompt wraps across lines
    assert "NEVER invent" in flat
    assert "ALREADY been calculated" in flat
    assert "ONLY JOB IS TO EXPLAIN" in flat


def test_the_model_never_receives_raw_sales_rows():
    """
    Structural guarantee: explain_action hands over only finished display values.
    If raw rows were ever passed, the model could recompute — and this test
    exists to make that regression loud.
    """
    import inspect
    source = inspect.getsource(E._display_payload)
    assert '"finding"' in source and '"evidence"' in source
    for forbidden in ("normalized_sales", "quantity", "stock_on_hand", "unit_price"):
        assert forbidden not in source
