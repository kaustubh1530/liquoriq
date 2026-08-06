"""
services/advisor/agent.py — PHASE 23: the agent loop.

    question + memory
        ↓
    base context (small, always present)
        ↓
    ┌── GPT-4o ──────────────────────────┐
    │  wants a tool?  → run it → feed back│  ← up to MAX_TOOL_ROUNDS
    │  no more tools? → final answer      │
    └─────────────────────────────────────┘
        ↓
    answer + the list of tools it actually called

WHY A LOOP RATHER THAN ONE CALL

One call with everything attached is a prompt, not an agent. The loop lets the
model ASK for what a question needs: "why are tequila sales down" pulls
category intelligence and then, having seen the answer, often pulls the product
list for that category. That second call is a decision made with information it
didn't have at the start — which is the thing that distinguishes an agent.

It also gives explainability for free. We don't ask the model which data it
used; we record which tools ran. A claimed citation and an observed one are
very different guarantees.

THE CALLER IS INJECTED. Same pattern as the Phase 22 explain layer: the OpenAI
client arrives as an argument so the whole loop is testable without the SDK,
without network, and without an API key.
"""

import json
import logging

from app.services.advisor import next_actions as NEXT
from app.services.advisor import signals as SIGNALS
from app.services.advisor import tools as TOOLS
from app.services.advisor.prompt import BRIEF_PROMPT, SYSTEM_PROMPT
from app.services.knowledge import service as KNOWLEDGE

logger = logging.getLogger(__name__)

# Enough for "look at categories, then look at the products inside the worst
# one, then answer". Beyond four the model is usually flailing, and each round
# is a paid API call.
MAX_TOOL_ROUNDS = 4

# How much conversation to carry. The advisor must understand that "what
# should I promote?" still refers to the Labor Day discussed two messages ago,
# but the whole history would eventually crowd out the store data.
MEMORY_TURNS = 8

FALLBACK = (
    "I can't reach my reasoning engine right now, so I don't want to guess at "
    "your numbers. Your dashboard and Business Intelligence page are still "
    "fully up to date — everything there is calculated without AI."
)


def _messages(question: str, base_context: dict, history: list[dict],
              knowledge_block: str = "") -> list[dict]:
    """
    System prompt → store context → prior turns → the question.

    The context goes in as a SYSTEM message rather than being glued onto the
    user's question. It is standing knowledge, not something the owner said,
    and models weight the two differently.
    """
    out = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content":
            "Here is the current state of this store. These figures are "
            "computed deterministically and are authoritative — use them, do "
            "not recompute them:\n\n"
            + json.dumps(base_context, indent=2, default=str)},
    ]
    # Knowledge sits AFTER the store's data and BEFORE the conversation: it
    # interprets his numbers, it does not supply them.
    if knowledge_block:
        out.append({"role": "system", "content": knowledge_block})
    for turn in (history or [])[-MEMORY_TURNS:]:
        role = turn.get("role")
        content = turn.get("content")
        if role in ("user", "assistant") and content:
            out.append({"role": role, "content": content})
    out.append({"role": "user", "content": question})
    return out


async def ask(question: str, base_context: dict, store_id, db,
              history: list[dict] | None = None, caller=None) -> dict:
    """
    Answer one question. Never raises.

    Returns {answer, tools_used, rounds, source}. `tools_used` is the honest
    citation list — the tools that actually ran, not the ones the model says it
    consulted.
    """
    if caller is None:
        from app.services.advisor.openai_agent import call_with_tools as caller

    # PHASE 24 — retrieve LiquorIQ's own playbooks, evaluate the business
    # rules against this store's numbers, and attach the industry benchmarks
    # BEFORE the model reasons. Never fatal: without it this degrades to the
    # Phase 23 advisor, which still works.
    knowledge = {"prompt_block": "", "citations": []}
    try:
        knowledge = await KNOWLEDGE.build(question, base_context, store_id, db)
    except Exception:  # noqa: BLE001
        logger.warning("Knowledge engine unavailable", exc_info=True)

    messages = _messages(question, base_context, history or [],
                         knowledge.get("prompt_block", ""))
    schema = TOOLS.openai_schema()
    used: list[dict] = []
    # The campaign this answer is about, if the advisor looked one up. Carried
    # into the Ad Creator link so the handoff keeps its subject.
    strategy_id: str | None = None
    logger.info("Advisor question received · %d chars · %d prior turns · %d tools",
                len(question), len(history or []), len(schema))

    for round_index in range(MAX_TOOL_ROUNDS):
        try:
            reply = await caller(messages, schema)
        except Exception as exc:  # noqa: BLE001 — the owner still gets an answer
            # exc_info AND the exception type. Logging only str(exc) hid an
            # ImportError behind a generic message for an entire debugging
            # session — the class name alone would have named the bug.
            logger.error("Advisor call failed on round %d · %s: %s",
                         round_index, type(exc).__name__, exc, exc_info=True)
            return {"answer": FALLBACK, "tools_used": used,
                    "rounds": round_index, "source": "unavailable",
                    "knowledge_used": knowledge.get("citations", []),
                    "error": f"{type(exc).__name__}: {exc}"}

        calls = reply.get("tool_calls") or []
        if not calls:
            answer = reply.get("content") or FALLBACK
            return {
                "answer": answer,
                "tools_used": used,
                "rounds": round_index + 1,
                "source": "ai",
                # Derived from what the advisor ACTUALLY looked at, so a button
                # can never point at a route the model invented.
                "next_actions": NEXT.derive(used, answer, strategy_id),
                "strategy_id": strategy_id,
                "knowledge_used": knowledge.get("citations", []),
            }

        # The model wants data. Run every tool it asked for, feed the results
        # back, and let it decide again with more information than before.
        messages.append({
            "role": "assistant",
            "content": reply.get("content"),
            "tool_calls": [
                {"id": c["id"], "type": "function",
                 "function": {"name": c["name"], "arguments": json.dumps(c["arguments"])}}
                for c in calls
            ],
        })

        logger.info("Advisor round %d · model requested tools: %s",
                    round_index, [c["name"] for c in calls])

        for call in calls:
            result = await TOOLS.execute(call["name"], call["arguments"], store_id, db)
            ok = "error" not in result
            if strategy_id is None:
                strategy_id = _strategy_from(result)
            logger.info("Advisor tool %s(%s) -> %s",
                        call["name"], call["arguments"],
                        "ok" if ok else result.get("error"))
            used.append({"tool": call["name"], "arguments": call["arguments"],
                         "ok": ok})
            messages.append({
                "role": "tool",
                "tool_call_id": call["id"],
                "content": json.dumps(result, default=str)[:12000],
            })

    # Out of rounds. Ask for a final answer with no tools available, so the
    # model is forced to conclude rather than requesting a fifth lookup.
    try:
        final = await caller(messages, None)
        answer = final.get("content") or FALLBACK
        return {"answer": answer, "tools_used": used,
                "rounds": MAX_TOOL_ROUNDS, "source": "ai",
                "next_actions": NEXT.derive(used, answer, strategy_id),
                "strategy_id": strategy_id,
                "knowledge_used": knowledge.get("citations", [])}
    except Exception as exc:  # noqa: BLE001
        logger.error("Advisor could not close out after tool rounds · %s: %s",
                     type(exc).__name__, exc, exc_info=True)
        return {"answer": FALLBACK, "tools_used": used,
                "rounds": MAX_TOOL_ROUNDS, "source": "unavailable",
                "error": f"{type(exc).__name__}: {exc}"}


async def generate_brief(base_context: dict, store_id, db, caller=None) -> dict:
    """
    Morning briefing. Separate entry point so the system instruction differs
    from a normal question without polluting the conversation history.
    """
    if not base_context.get("has_data"):
        return {
            "answer": "You haven't uploaded a sales report yet. Once you do, I "
                      "can tell you what to reorder, what to clear and what to "
                      "promote.",
            "tools_used": [], "rounds": 0, "source": "deterministic",
        }

    if caller is None:
        from app.services.advisor.openai_agent import call_with_tools as caller

    # Unusual situations, detected deterministically. Asking a model to "notice
    # anything interesting" is an invitation to invent something interesting;
    # it is given the findings and explains them.
    try:
        found = await SIGNALS.detect(store_id, db, base_context)
    except Exception:  # noqa: BLE001 — a quieter briefing, not a failed one
        logger.warning("Signal detection failed", exc_info=True)
        found = []

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": BRIEF_PROMPT},
        {"role": "system", "content":
            "Current state of the store:\n\n"
            + json.dumps(base_context, indent=2, default=str)},
    ]
    if found:
        messages.append({"role": "system", "content":
            "SIGNALS — unusual situations detected in this store's data, most "
            "urgent first. Lead with the most important one:\n\n"
            + json.dumps(found, indent=2, default=str)})
    messages.append({"role": "user", "content": "Write my briefing for today."})

    schema = TOOLS.openai_schema()
    used: list[dict] = []

    for _ in range(2):   # a briefing needs one lookup at most
        try:
            reply = await caller(messages, schema)
        except Exception as exc:  # noqa: BLE001
            logger.error("Advisor brief unavailable · %s: %s",
                         type(exc).__name__, exc, exc_info=True)
            return {"answer": _deterministic_brief(base_context, found),
                    "tools_used": used, "rounds": 0, "source": "deterministic",
                    "signals": found, "error": f"{type(exc).__name__}: {exc}"}

        calls = reply.get("tool_calls") or []
        if not calls:
            return {"answer": reply.get("content") or _deterministic_brief(base_context),
                    "tools_used": used, "rounds": 1, "source": "ai",
                    "signals": found}

        messages.append({
            "role": "assistant", "content": reply.get("content"),
            "tool_calls": [
                {"id": c["id"], "type": "function",
                 "function": {"name": c["name"], "arguments": json.dumps(c["arguments"])}}
                for c in calls
            ],
        })
        logger.info("Advisor round %d · model requested tools: %s",
                    round_index, [c["name"] for c in calls])

        for call in calls:
            result = await TOOLS.execute(call["name"], call["arguments"], store_id, db)
            ok = "error" not in result
            if strategy_id is None:
                strategy_id = _strategy_from(result)
            logger.info("Advisor tool %s(%s) -> %s",
                        call["name"], call["arguments"],
                        "ok" if ok else result.get("error"))
            used.append({"tool": call["name"], "arguments": call["arguments"],
                         "ok": ok})
            messages.append({"role": "tool", "tool_call_id": call["id"],
                             "content": json.dumps(result, default=str)[:12000]})
        schema = None   # second pass: conclude, don't fetch again

    return {"answer": _deterministic_brief(base_context, found), "tools_used": used,
            "rounds": 2, "source": "deterministic", "signals": found}


def _strategy_from(result: dict) -> str | None:
    """
    The most recent strategy id in a tool result, if there is one.

    Newest first because ai_strategies returns them in that order — the advisor
    talking about "your Labor Day campaign" almost always means the latest one.
    """
    if not isinstance(result, dict):
        return None
    for row in (result.get("strategies") or []):
        if isinstance(row, dict) and row.get("id"):
            return str(row["id"])
    return None


def _deterministic_brief(ctx: dict, signals: list[dict] | None = None) -> str:
    """
    The briefing without AI, written from the same figures.

    The advisor page must not be blank because OpenAI is down or out of credit.
    This is deliberately plain — it exists to be correct, not charming.
    """
    health = ctx.get("business_health", {})
    nums = ctx.get("headline_numbers", {})
    actions = ctx.get("top_actions", [])

    parts = []
    # Lead with what changed or is about to, exactly as the AI version would —
    # a health score that hasn't moved is not news.
    if signals:
        parts.append(f"{signals[0]['headline']}. {signals[0]['detail']}")
    parts.append(
        f"Your business health is {health.get('score')} out of 100 "
        f"({health.get('band')}). {health.get('verdict', '')}".strip()
    )
    if nums.get("slow_stock_pct"):
        parts.append(
            f"{nums['slow_stock_pct']}% of your stock value is sitting in products "
            f"that are barely selling, and your inventory turns over "
            f"{nums.get('inventory_turnover')} times a year against a healthy 4–6."
        )
    if actions:
        top = actions[0]
        parts.append(
            f"Your highest-value move is: {top['title'].lower()} — worth about "
            f"{top['impact']}, {(top.get('timeline') or 'this week').lower()}."
        )
    return " ".join(parts)
