"""
services/knowledge/service.py — PHASE 24: the Knowledge Engine's front door.

    question + store context
              ↓
    ┌─────────────────────────────────┐
    │ retrieve   relevant playbooks    │  ← RAG
    │ evaluate   business rules        │  ← deterministic, outranks the model
    │ interpret  industry benchmarks   │  ← what "good" looks like
    └─────────────────────────────────┘
              ↓
    one prompt block + a citation list

THE PRIORITY ORDER IS THE PRODUCT

  1. BUSINESS RULES   — hard constraints checked against his actual numbers.
                        The model cannot argue with these.
  2. STORE DATA       — measured from his own report (supplied by the agent).
  3. PLAYBOOKS        — LiquorIQ's own retail knowledge. Advice, not fact.
  4. BENCHMARKS       — industry ranges, explicitly not his history.
  5. GPT REASONING    — everything left over.

The model sees them in that order and is told the order. A recommendation that
violates a rule is not a matter of taste; it is wrong, and the rule names the
specific products it applies to so there is nothing to interpret.
"""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.knowledge import benchmarks as BENCH
from app.services.knowledge import rules as RULES
from app.services.knowledge.retriever import get_retriever

logger = logging.getLogger(__name__)

# Enough for two or three playbook sections. More crowds out the store's own
# data, which always matters more than general advice.
DEFAULT_CHUNKS = 5

# Below this the match is incidental — a shared common word rather than a real
# topical hit. Feeding weak chunks in is worse than feeding none.
MIN_SCORE = 1.5


async def build(question: str, base_context: dict,
                store_id: uuid.UUID | None = None,
                db: AsyncSession | None = None,
                products: list[dict] | None = None,
                deals: list[dict] | None = None,
                segments: dict | None = None,
                k: int = DEFAULT_CHUNKS) -> dict:
    """
    Everything the advisor should know before it reasons.

    Never raises: a knowledge failure must degrade to "GPT plus store data",
    which is still the Phase 23 product. The engine adds to the advisor; it is
    not load-bearing for it.
    """
    retrieved: list[dict] = []
    try:
        hits = get_retriever().search(question, k=k)
        retrieved = [h for h in hits if h["score"] >= MIN_SCORE]
        logger.info("Knowledge retrieval · %d chunks above threshold · %s",
                    len(retrieved), [h["doc_id"] for h in retrieved])
    except Exception:  # noqa: BLE001
        logger.warning("Knowledge retrieval failed", exc_info=True)

    active_rules: list[dict] = []
    try:
        active_rules = RULES.evaluate(base_context, products, deals, segments)
    except Exception:  # noqa: BLE001
        logger.warning("Rule evaluation failed", exc_info=True)

    return {
        "prompt_block": _assemble(retrieved, active_rules, base_context),
        "citations": _citations(retrieved, active_rules),
        "chunks_retrieved": len(retrieved),
        "rules_active": len(active_rules),
    }


def _assemble(retrieved: list[dict], active_rules: list[dict],
              base_context: dict) -> str:
    """One system message, ordered by authority."""
    parts: list[str] = []

    rules_block = RULES.as_prompt_block(active_rules)
    if rules_block:
        parts.append(rules_block)

    if retrieved:
        lines = [
            "LIQUORIQ PLAYBOOK — our own retail knowledge, retrieved because it "
            "is relevant to this question. This is EXPERIENCE, not measurement: "
            "use it to interpret and to advise, never as a source of figures "
            "about this store. When you draw on it, say so."
        ]
        for hit in retrieved:
            lines.append(f"\n--- {hit['citation']} ---\n{hit['text']}")
        parts.append("\n".join(lines))

    bench_block = BENCH.as_prompt_block(base_context)
    if bench_block:
        parts.append(bench_block)

    if parts:
        parts.append(
            "SOURCE PRIORITY — when these disagree, this is the order:\n"
            "1. Business rules (hard constraints, checked against his numbers)\n"
            "2. This store's own measured data\n"
            "3. The LiquorIQ playbook\n"
            "4. Industry benchmarks\n"
            "5. Your own judgement\n\n"
            "Label where each recommendation came from: store data, LiquorIQ "
            "playbook, industry benchmark, or your own reasoning."
        )

    return "\n\n".join(parts)


def _citations(retrieved: list[dict], active_rules: list[dict]) -> list[dict]:
    """
    What the UI shows. Observed, not claimed — exactly like tools_used: these
    are the chunks that were actually retrieved and the rules that actually
    fired, recorded as it happened.
    """
    out = [
        {"kind": "playbook", "label": hit["citation"], "doc_id": hit["doc_id"],
         "domain": hit["domain"], "score": hit["score"]}
        for hit in retrieved
    ]
    out += [
        {"kind": "rule", "label": rule["statement"], "doc_id": rule["rule"],
         "applies_to": rule.get("applies_to", [])}
        for rule in active_rules
    ]
    return out


def catalogue() -> list[dict]:
    """Every playbook in the base, for the transparency endpoint."""
    seen: dict[str, dict] = {}
    for chunk in get_retriever().chunks:
        entry = seen.setdefault(chunk.doc_id, {
            "doc_id": chunk.doc_id, "title": chunk.title,
            "domain": chunk.domain, "keywords": chunk.keywords, "sections": [],
        })
        entry["sections"].append(chunk.section)
    return sorted(seen.values(), key=lambda d: (d["domain"], d["title"]))
