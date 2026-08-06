"""
tests/test_advisor_agent.py — PHASE 23: the agent loop, without OpenAI.

The entire loop is exercised with a fake caller: no API key, no network, no
SDK. That is the payoff of injecting the model client rather than importing it
— the thing worth testing here is the ORCHESTRATION (does it call tools, feed
results back, stop when it should, degrade when the model is down), and none of
that needs a real model.

What is under test:
  · a question with no tool call returns the answer directly
  · a tool request is executed and fed back
  · multi-round reasoning works (tools → more tools → answer)
  · the loop cannot spin forever
  · tools_used is what ACTUALLY RAN, not what the model claims
  · a broken tool degrades to an error string, not a 500
  · OpenAI being down still produces something useful
  · conversation memory is carried into the prompt
"""

import asyncio
from datetime import date

import pytest

from app.services.advisor import agent as AGENT
from app.services.advisor import tools as TOOLS

_LOOP = asyncio.new_event_loop()


def _run(coro):
    """A private loop — asyncio.run() would close the shared one and break the
    SMS tests, and get_event_loop() is deprecated when none is running."""
    return _LOOP.run_until_complete(coro)


CONTEXT = {
    "store_name": "Classy Corks", "has_data": True,
    "business_health": {"score": 39.4, "band": "at risk"},
    "headline_numbers": {"slow_stock_pct": 70.4, "inventory_turnover": 2.46},
    "top_actions": [{"priority": "P1", "title": "$220,661 is frozen",
                     "impact": "$132,396", "timeline": "This quarter",
                     "confidence": "high", "type": "clearance"}],
}


def caller_returning(*replies):
    """A fake model that returns each scripted reply in turn."""
    queue = list(replies)

    async def fake(messages, tools):
        fake.calls.append({"messages": messages, "tools": tools})
        return queue.pop(0) if queue else {"content": "done", "tool_calls": []}
    fake.calls = []
    return fake


def text(content):
    return {"content": content, "tool_calls": []}


def wants(name, args=None, call_id="c1"):
    return {"content": None,
            "tool_calls": [{"id": call_id, "name": name, "arguments": args or {}}]}


# ── The loop ─────────────────────────────────────────────────────────────────

def test_a_question_needing_no_lookup_answers_directly():
    fake = caller_returning(text("115 products are sold out."))
    out = _run(AGENT.ask("How many are sold out?", CONTEXT, "store", None, caller=fake))
    assert out["answer"] == "115 products are sold out."
    assert out["tools_used"] == []
    assert out["rounds"] == 1


def test_a_tool_request_is_executed_and_fed_back(monkeypatch):
    async def fake_tool(store_id, db, **kw):
        return {"categories": [{"category": "Tequila", "revenue": 12800}]}
    monkeypatch.setitem(TOOLS.REGISTRY, "category_intelligence",
                        {**TOOLS.REGISTRY["category_intelligence"], "fn": fake_tool})

    fake = caller_returning(wants("category_intelligence"),
                            text("Tequila did $12,800 last month."))
    out = _run(AGENT.ask("How is tequila doing?", CONTEXT, "store", None, caller=fake))

    assert out["tools_used"] == [{"tool": "category_intelligence",
                                  "arguments": {}, "ok": True}]
    # The tool's output must reach the model, or the second call is blind.
    second = fake.calls[1]["messages"]
    assert any(m.get("role") == "tool" and "Tequila" in m["content"] for m in second)


def test_the_agent_can_reason_across_several_rounds(monkeypatch):
    """
    The thing that makes this an agent: the second lookup is chosen using
    information the model did not have when it made the first.
    """
    async def fake_tool(store_id, db, **kw):
        return {"ok": True}
    for name in ("category_intelligence", "inventory_intelligence"):
        monkeypatch.setitem(TOOLS.REGISTRY, name,
                            {**TOOLS.REGISTRY[name], "fn": fake_tool})

    fake = caller_returning(
        wants("category_intelligence", call_id="a"),
        wants("inventory_intelligence", {"category": "Tequila"}, call_id="b"),
        text("Here is what's happening with tequila."),
    )
    out = _run(AGENT.ask("Why are tequila sales down?", CONTEXT, "store", None, caller=fake))

    assert [t["tool"] for t in out["tools_used"]] == \
        ["category_intelligence", "inventory_intelligence"]
    assert out["rounds"] == 3


def test_the_loop_cannot_spin_forever(monkeypatch):
    """A model that keeps asking for tools must still be made to conclude."""
    async def fake_tool(store_id, db, **kw):
        return {"ok": True}
    monkeypatch.setitem(TOOLS.REGISTRY, "action_center",
                        {**TOOLS.REGISTRY["action_center"], "fn": fake_tool})

    greedy = caller_returning(*([wants("action_center")] * 10))
    out = _run(AGENT.ask("What should I do?", CONTEXT, "store", None, caller=greedy))
    assert len(out["tools_used"]) <= AGENT.MAX_TOOL_ROUNDS
    assert out["answer"]


def test_the_final_round_is_asked_without_tools(monkeypatch):
    """Otherwise the model just requests a fifth lookup and we loop again."""
    async def fake_tool(store_id, db, **kw):
        return {"ok": True}
    monkeypatch.setitem(TOOLS.REGISTRY, "action_center",
                        {**TOOLS.REGISTRY["action_center"], "fn": fake_tool})

    greedy = caller_returning(*([wants("action_center")] * 10))
    _run(AGENT.ask("What should I do?", CONTEXT, "store", None, caller=greedy))
    assert greedy.calls[-1]["tools"] is None


# ── Explainability ───────────────────────────────────────────────────────────

def test_tools_used_records_what_ran_not_what_was_claimed(monkeypatch):
    """
    A model's account of its own sources is not evidence. The citation list is
    built from execution, so it cannot be embellished.
    """
    async def fake_tool(store_id, db, **kw):
        return {"ok": True}
    monkeypatch.setitem(TOOLS.REGISTRY, "customer_segments",
                        {**TOOLS.REGISTRY["customer_segments"], "fn": fake_tool})

    fake = caller_returning(
        wants("customer_segments"),
        text("I reviewed your inventory, categories and campaign history."),
    )
    out = _run(AGENT.ask("Who should I text?", CONTEXT, "store", None, caller=fake))
    assert [t["tool"] for t in out["tools_used"]] == ["customer_segments"]


def test_a_failing_tool_is_reported_not_fatal():
    """The owner asked a question; he deserves an answer about what did work."""
    async def boom(store_id, db, **kw):
        raise RuntimeError("database on fire")

    original = TOOLS.REGISTRY["supplier_deals"]["fn"]
    TOOLS.REGISTRY["supplier_deals"]["fn"] = boom
    try:
        fake = caller_returning(wants("supplier_deals"),
                                text("I couldn't read your deals."))
        out = _run(AGENT.ask("Any good deals?", CONTEXT, "store", None, caller=fake))
        assert out["tools_used"][0]["ok"] is False
        assert out["answer"]
    finally:
        TOOLS.REGISTRY["supplier_deals"]["fn"] = original


def test_an_unknown_tool_name_does_not_crash():
    result = _run(TOOLS.execute("not_a_real_tool", {}, "store", None))
    assert "error" in result


def test_bad_tool_arguments_are_reported_clearly():
    result = _run(TOOLS.execute("category_intelligence", {"nonsense": 1}, "store", None))
    assert "error" in result


# ── Degradation ──────────────────────────────────────────────────────────────

def test_openai_being_down_still_returns_something_useful():
    async def dead(messages, tools):
        raise RuntimeError("out of credits")
    out = _run(AGENT.ask("What should I do?", CONTEXT, "store", None, caller=dead))
    assert out["source"] == "unavailable"
    assert "dashboard" in out["answer"].lower()


def test_the_brief_falls_back_to_deterministic_prose():
    async def dead(messages, tools):
        raise RuntimeError("network")
    out = _run(AGENT.generate_brief(CONTEXT, "store", None, caller=dead))
    assert out["source"] == "deterministic"
    assert "39.4" in out["answer"]
    assert "132,396" in out["answer"]


def test_the_brief_says_so_when_there_is_no_data():
    out = _run(AGENT.generate_brief({"has_data": False}, "store", None, caller=None))
    assert out["source"] == "deterministic"
    assert "upload" in out["answer"].lower()


# ── Memory ───────────────────────────────────────────────────────────────────

def test_prior_turns_are_carried_into_the_prompt():
    """
    "What should I promote?" is meaningless without "I'm thinking about Labor
    Day" two messages earlier.
    """
    history = [
        {"role": "user", "content": "I'm thinking about Labor Day."},
        {"role": "assistant", "content": "Labor Day is 28 days away."},
    ]
    fake = caller_returning(text("Promote beer and seltzer."))
    _run(AGENT.ask("What should I promote?", CONTEXT, "store", None,
                   history=history, caller=fake))

    sent = fake.calls[0]["messages"]
    assert any("Labor Day" in (m.get("content") or "") for m in sent)


def test_memory_is_capped_so_store_data_is_never_crowded_out():
    history = [{"role": "user", "content": f"question {i}"} for i in range(40)]
    fake = caller_returning(text("ok"))
    _run(AGENT.ask("And now?", CONTEXT, "store", None, history=history, caller=fake))

    sent = fake.calls[0]["messages"]
    carried = [m for m in sent if (m.get("content") or "").startswith("question ")]
    assert len(carried) <= AGENT.MEMORY_TURNS


def test_the_store_context_is_a_system_message_not_part_of_the_question():
    """Standing knowledge, not something the owner said — models weight the
    two differently."""
    fake = caller_returning(text("ok"))
    _run(AGENT.ask("Hello", CONTEXT, "store", None, caller=fake))

    sent = fake.calls[0]["messages"]
    context_msgs = [m for m in sent
                    if m["role"] == "system" and "Classy Corks" in (m.get("content") or "")]
    assert len(context_msgs) == 1
    assert sent[-1] == {"role": "user", "content": "Hello"}


# ── The tool registry itself ─────────────────────────────────────────────────

def test_every_tool_is_exposed_to_the_model():
    names = {t["function"]["name"] for t in TOOLS.openai_schema()}
    assert names == set(TOOLS.REGISTRY)


def test_every_tool_describes_when_to_use_it():
    """A tool the model can't tell apart from another is a tool it won't use."""
    for name, spec in TOOLS.REGISTRY.items():
        assert len(spec["description"]) > 60, name
        assert "use" in spec["description"].lower(), name


def test_the_schema_is_valid_openai_shape():
    for tool in TOOLS.openai_schema():
        assert tool["type"] == "function"
        assert tool["function"]["parameters"]["type"] == "object"
        assert isinstance(tool["function"]["parameters"]["properties"], dict)


@pytest.mark.parametrize("name", list(TOOLS.REGISTRY))
def test_no_tool_calculates_anything(name):
    """
    Tools ADAPT existing services. If one started doing its own arithmetic
    there would be two sources of truth for the same figure and the advisor
    would eventually contradict the dashboard.
    """
    import inspect
    source = inspect.getsource(TOOLS.REGISTRY[name]["fn"])
    for operator in (" * ", " / ", "sum(", "round("):
        assert operator not in source, f"{name} appears to compute: {operator!r}"


# ── The prompt ───────────────────────────────────────────────────────────────

def test_the_prompt_forbids_inventing_numbers():
    from app.services.advisor.prompt import SYSTEM_PROMPT
    flat = " ".join(SYSTEM_PROMPT.split())
    assert "NEVER INVENT A NUMBER" in flat
    # Phase 23.5: the rigid decline phrase was replaced by a requirement to
    # explain WHY the data is missing and what would fix it. Refusing to guess
    # is still mandatory; sounding like an error message is not.
    assert "never a made-up figure" in flat


def test_the_prompt_requires_the_decision_format():
    """
    Phase 23.5 replaced six mandatory headings with four, used only for
    DECISION questions. Six headings on "how many are sold out?" is ceremony,
    and ceremony reads as software rather than as a consultant.
    """
    from app.services.advisor.prompt import SYSTEM_PROMPT
    for heading in ("## What I'd do", "## Why", "## The trade-off", "## Next step"):
        assert heading in SYSTEM_PROMPT


def test_the_prompt_forbids_reciting_metrics():
    """The dashboard already showed him the number. The advisor's job is the
    so-what."""
    from app.services.advisor.prompt import SYSTEM_PROMPT
    flat = " ".join(SYSTEM_PROMPT.split())
    assert "NEVER JUST RECITE A METRIC" in flat
    assert "SO WHAT" in flat


def test_the_prompt_demands_ranking_over_dumping():
    from app.services.advisor.prompt import SYSTEM_PROMPT
    flat = " ".join(SYSTEM_PROMPT.split())
    assert "RANK, DON'T DUMP" in flat
    assert "466 slow products" in flat   # the actual failure it was written for


def test_the_prompt_demands_money_and_time_on_every_recommendation():
    from app.services.advisor.prompt import SYSTEM_PROMPT
    flat = " ".join(SYSTEM_PROMPT.split())
    assert "MONEY AND TIME" in flat
    assert "Before [holiday]" in flat


def test_the_prompt_demands_the_tradeoff():
    from app.services.advisor.prompt import SYSTEM_PROMPT
    flat = " ".join(SYSTEM_PROMPT.split())
    assert "NAME THE TRADE-OFF" in flat


def test_the_prompt_requires_provenance_labels():
    from app.services.advisor.prompt import SYSTEM_PROMPT
    for label in ("measured", "estimated", "industry rate", "predicted"):
        assert label in SYSTEM_PROMPT


def test_the_prompt_explains_missing_data_rather_than_shrugging():
    from app.services.advisor.prompt import SYSTEM_PROMPT
    flat = " ".join(SYSTEM_PROMPT.split())
    assert "EXPLAIN WHY AND WHAT WOULD FIX IT" in flat
    assert "monthly summary" in flat


def test_the_prompt_caps_length():
    """"Do not be more verbose" was an explicit requirement."""
    from app.services.advisor.prompt import SYSTEM_PROMPT
    assert "150-250 words" in SYSTEM_PROMPT or "150–250 words" in SYSTEM_PROMPT


def test_the_prompt_names_only_real_workflows():
    """A recommendation to use a feature that doesn't exist is worse than none."""
    from app.services.advisor.prompt import WORKFLOWS
    for real in ("Generate Campaign", "Create Ad", "Create Shelf Labels",
                 "Open Inventory", "View Customers", "Business Intelligence"):
        assert real in WORKFLOWS


def test_industry_knowledge_may_not_supply_figures():
    from app.services.advisor.prompt import INDUSTRY
    assert "does not supply figures" in INDUSTRY


def test_the_prompt_warns_that_inventory_is_at_retail():
    """The Phase 22 lesson, carried into the advisor's mouth."""
    from app.services.advisor.prompt import SYSTEM_PROMPT
    flat = " ".join(SYSTEM_PROMPT.split())
    assert "RETAIL" in flat
    assert "not what he paid" in flat.lower() or "NOT what he paid" in flat


# ── The outage: an ImportError disguised as a rate limit ─────────────────────

def test_the_openai_adapter_imports_the_names_it_actually_uses():
    """
    THE PHASE 23 OUTAGE, IN ONE TEST.

    openai_agent.py did `from app.config import settings`, but app.config only
    exposes get_settings(). That ImportError fired inside agent.ask()'s lazy
    import, was caught by the agent's own "never raise" guard, and became
    "I couldn't reach my reasoning engine" — for every question, without OpenAI
    ever being contacted.

    Checked by reading the source rather than importing, so the test runs
    without the OpenAI SDK installed.
    """
    import ast
    import pathlib

    import app.config as config

    source = pathlib.Path("app/services/advisor/openai_agent.py").read_text()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "app.config":
            for alias in node.names:
                assert hasattr(config, alias.name), (
                    f"openai_agent.py imports app.config.{alias.name}, which "
                    f"does not exist. Every advisor question will fall back."
                )


def test_only_rate_limits_are_translated_into_a_quota_message():
    """
    Every exception used to be routed through _quota_message(), which returns
    "OpenAI is rate limiting us" for anything it doesn't recognise. An auth
    failure, a bad schema and a network timeout all arrived wearing the same
    disguise, and the real cause was destroyed at the boundary.
    """
    import pathlib
    source = pathlib.Path("app/services/advisor/openai_agent.py").read_text()

    assert "except RateLimitError" in source, \
        "rate limits must be caught specifically, not as a bare Exception"
    quota_line = next(l for l in source.splitlines() if "_quota_message(exc)" in l)
    block = source[:source.index(quota_line)]
    assert block.rstrip().endswith(
        tuple(("exc_info=True)", "RateLimitError as exc:"))
    ) or "RateLimitError" in block[-400:], \
        "_quota_message must only be reached from the RateLimitError branch"


def test_a_failed_round_carries_the_real_exception_out():
    """
    The fallback message alone is undebuggable from the outside. The exception
    type and message must reach the caller, and therefore the API response.
    """
    async def dead(messages, tools):
        raise ValueError("something very specific went wrong")

    out = _run(AGENT.ask("What should I do?", CONTEXT, "store", None, caller=dead))
    assert out["source"] == "unavailable"
    assert "ValueError" in out["error"]
    assert "something very specific" in out["error"]


def test_a_failed_brief_carries_the_real_exception_out():
    async def dead(messages, tools):
        raise ConnectionError("dns is down")

    out = _run(AGENT.generate_brief(CONTEXT, "store", None, caller=dead))
    assert out["source"] == "deterministic"
    assert "ConnectionError" in out["error"]


# ═══ PHASE 23.5 · consultant behaviour ═══════════════════════════════════════

from app.services.advisor import next_actions as NEXT   # noqa: E402


# ── Next actions: derived, never generated ───────────────────────────────────

def test_every_answer_ends_with_something_clickable():
    assert NEXT.derive([], "") != []


def test_the_buttons_come_from_the_tools_that_ran():
    """
    Derived rather than generated, so a model that invents /clearance-wizard
    cannot produce a dead link. A dead link reads as a broken product.
    """
    out = NEXT.derive([{"tool": "customer_segments", "ok": True}], "")
    assert any(a["route"] == "/customers" for a in out)


def test_a_failed_tool_does_not_earn_a_button():
    out = NEXT.derive([{"tool": "customer_segments", "ok": False}], "")
    assert not any(a["route"] == "/customers" for a in out)


def test_an_explicit_recommendation_outranks_the_tools_used():
    """"Run a clearance" is a stronger signal than "inventory was consulted"."""
    out = NEXT.derive([{"tool": "inventory_intelligence", "ok": True}],
                      "I'd run a clearance on the slowest twenty.")
    assert out[0]["route"] == "/ai?focus=clearance"


def test_buttons_are_capped_so_they_are_not_a_menu():
    out = NEXT.derive(
        [{"tool": t, "ok": True} for t in NEXT.BY_TOOL],
        "clearance, shelf labels, an advertisement, text them, upload")
    assert len(out) <= NEXT.MAX_ACTIONS


def test_buttons_are_never_duplicated():
    out = NEXT.derive([{"tool": "action_center", "ok": True},
                       {"tool": "customer_segments", "ok": True}], "")
    assert len({a["route"] for a in out}) == len(out)


def test_every_route_a_button_can_produce_exists_in_the_app():
    """A recommendation pointing at a 404 is worse than no recommendation."""
    import pathlib
    routes = pathlib.Path("../frontend/src/App.jsx").read_text()
    everywhere = [a for group in NEXT.BY_TOOL.values() for a in group]
    everywhere += [a for _, a in NEXT.BY_INTENT] + NEXT.DEFAULT
    for action in everywhere:
        path = action["route"].split("?")[0]
        assert f'path="{path}"' in routes, f"{path} is not a real route"


# ── Signals: detected, not imagined ──────────────────────────────────────────

def test_a_store_with_no_data_produces_no_signals():
    from app.services.advisor import signals as SIGNALS
    assert _run(SIGNALS.detect("store", None, {"has_data": False})) == []


def test_stock_outs_are_the_most_urgent_signal():
    from app.services.advisor import signals as SIGNALS
    ctx = {"has_data": True, "stock_class_counts": {"sold_out": 115, "sleeping": 202},
           "reporting_period": {"end": str(date.today())}}
    found = _run(SIGNALS.detect("store", None, ctx))
    assert found[0]["kind"] == "stock_outs"
    assert "115" in found[0]["headline"]


def test_stale_data_is_flagged_so_advice_is_not_trusted_blindly():
    from datetime import timedelta

    from app.services.advisor import signals as SIGNALS
    old = date.today() - timedelta(days=40)
    ctx = {"has_data": True, "stock_class_counts": {},
           "reporting_period": {"end": str(old)}}
    found = _run(SIGNALS.detect("store", None, ctx))
    assert any(s["kind"] == "stale_data" for s in found)


def test_fresh_data_is_not_flagged():
    from app.services.advisor import signals as SIGNALS
    ctx = {"has_data": True, "stock_class_counts": {},
           "reporting_period": {"end": str(date.today())}}
    found = _run(SIGNALS.detect("store", None, ctx))
    assert not any(s["kind"] == "stale_data" for s in found)


def test_signals_are_capped_and_ordered_by_urgency():
    from app.services.advisor import signals as SIGNALS
    ctx = {"has_data": True,
           "stock_class_counts": {"sold_out": 115, "sleeping": 202},
           "reporting_period": {"end": "2020-01-01"}}
    found = _run(SIGNALS.detect("store", None, ctx))
    assert len(found) <= 4
    assert [s["urgency"] for s in found] == sorted(s["urgency"] for s in found)


def test_every_signal_states_whether_it_is_measured():
    from app.services.advisor import signals as SIGNALS
    ctx = {"has_data": True, "stock_class_counts": {"sold_out": 5, "sleeping": 50},
           "reporting_period": {"end": "2020-01-01"}}
    for signal in _run(SIGNALS.detect("store", None, ctx)):
        assert signal["basis"] in ("measured", "estimated")
        assert signal["headline"] and signal["detail"]


def test_the_offline_brief_leads_with_the_signal_not_the_score():
    """A health score that hasn't moved is not news."""
    out = AGENT._deterministic_brief(
        CONTEXT, [{"urgency": 1, "kind": "stock_outs",
                   "headline": "115 products are out of stock",
                   "detail": "Every day costs a sale.", "basis": "measured"}])
    assert out.startswith("115 products are out of stock")


# ── Ranking: the model receives ordered data ─────────────────────────────────

def test_inventory_results_declare_how_they_are_ranked():
    """"You have 466 slow products" is not advice. The top ten by money is."""
    import inspect
    source = inspect.getsource(TOOLS.inventory_intelligence)
    assert "ranked_by" in source
    assert "cash_frozen" in source and "money_at_stake" in source
