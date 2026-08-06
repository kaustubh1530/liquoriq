"""
tests/test_knowledge_engine.py — PHASE 24: RAG, rules and benchmarks.

Retrieval is DETERMINISTIC, which is the property that makes this testable at
all: the same question retrieves the same playbook every run, with no API key
and no network. An embedding index would make these tests either flaky or
mocked into meaninglessness.

Three things under test:
  · retrieval puts the right playbook in front of the model
  · business rules fire on the store's real numbers and are phrased as
    constraints the model cannot argue with
  · benchmarks interpret rather than compute, and say they are industry figures
"""

import pytest

from app.services.knowledge import benchmarks as BENCH
from app.services.knowledge import rules as RULES
from app.services.knowledge.retriever import (LexicalRetriever, load_chunks,
                                              tokenise)

CHUNKS = load_chunks()
RETRIEVER = LexicalRetriever(CHUNKS)


def top_docs(query, k=4):
    return [h["doc_id"] for h in RETRIEVER.search(query, k=k)]


# ── The corpus itself ────────────────────────────────────────────────────────

def test_the_knowledge_base_loads():
    assert len(CHUNKS) > 80, "the playbook corpus did not load"


def test_every_playbook_declares_its_metadata():
    """Frontmatter drives routing. A document without it is unreachable."""
    for chunk in CHUNKS:
        assert chunk.title, chunk.doc_id
        assert chunk.domain, chunk.doc_id
        assert chunk.keywords, f"{chunk.doc_id} has no keywords"


def test_chunks_are_whole_sections_not_arbitrary_windows():
    """
    Chunked on '##' headers so a retrieved chunk is a complete thought.
    "Common mistakes" sliced in half is worse than not retrieving it.
    """
    for chunk in CHUNKS:
        assert chunk.section
        assert len(chunk.text) >= 40


def test_every_playbook_carries_ai_notes():
    """
    The AI notes section is where an operator's judgement becomes a constraint
    the model can act on. A playbook without one is prose.
    """
    with_notes = {c.doc_id for c in CHUNKS if c.section.lower().startswith("ai notes")}
    all_docs = {c.doc_id for c in CHUNKS}
    assert with_notes == all_docs, f"missing AI notes: {all_docs - with_notes}"


# ── Retrieval quality ────────────────────────────────────────────────────────

@pytest.mark.parametrize("question,expected", [
    ("How should I prepare for Labor Day?", "holiday/labor_day"),
    ("Why is my inventory unhealthy?", "retail/inventory"),
    ("Should I take this supplier deal?", "pricing/supplier_deals"),
    ("How should I promote Cabernet?", "categories/wine"),
    ("Should I discount Tito's vodka?", "pricing/discounts"),
    ("How do I get more repeat customers?", "retail/customers"),
    ("Where should I put my end caps?", "retail/merchandising"),
    ("What should I text my customers?", "marketing/sms"),
    ("What bourbon should I stock?", "categories/whiskey"),
    ("How much cash is stuck on my shelves?", "retail/cashflow"),
])
def test_the_right_playbook_is_retrieved(question, expected):
    assert expected in top_docs(question), \
        f"{question!r} did not retrieve {expected}; got {top_docs(question)}"


def test_an_unrelated_question_retrieves_nothing_strong():
    """Weak matches are worse than none — they crowd out the store's own data."""
    hits = RETRIEVER.search("what is the capital of France", k=5)
    assert all(h["score"] < 5 for h in hits)


def test_scoring_prefers_the_specific_over_the_generic():
    """"mezcal" should beat the eight documents that merely say "stock"."""
    hits = RETRIEVER.search("mezcal", k=3)
    assert hits and hits[0]["doc_id"] == "categories/tequila"


def test_retrieval_is_deterministic():
    assert top_docs("How should I prepare for Labor Day?") == \
           top_docs("How should I prepare for Labor Day?")


def test_domain_filtering_works():
    hits = RETRIEVER.search("what should I stock", k=5, domain="categories")
    assert all(h["domain"] == "categories" for h in hits)


def test_stopwords_do_not_carry_signal():
    assert tokenise("what is the of and my") == []


# ── Business rules ───────────────────────────────────────────────────────────

CONTEXT = {"headline_numbers": {"valuation_basis": "retail",
                                "inventory_turnover": 2.46,
                                "sell_through_rate": 0.176},
           "business_health": {"score": 39.4}}

FAST = {"product_name": "Titos 1.75L", "weeks_of_supply": 1.8,
        "units_sold": 40, "stock": 12, "inventory_value": 260}
HEAVY = {"product_name": "Slow Cognac", "weeks_of_supply": 90.0,
         "units_sold": 1, "stock": 40, "inventory_value": 1800}
EMPTY = {"product_name": "Bulleit 1.75L", "weeks_of_supply": None,
         "units_sold": 6, "stock": 0, "inventory_value": 0}


def test_a_fast_mover_triggers_the_no_discount_rule():
    active = RULES.evaluate(CONTEXT, [FAST])
    rule = next(r for r in active if r["rule"] == "no_discount_fast_movers")
    assert "Titos 1.75L" in rule["applies_to"]


def test_an_overstocked_product_triggers_the_no_reorder_rule():
    active = RULES.evaluate(CONTEXT, [HEAVY])
    rule = next(r for r in active if r["rule"] == "no_reorder_overstocked")
    assert "Slow Cognac" in rule["applies_to"]


def test_a_sold_out_product_may_not_be_promoted():
    active = RULES.evaluate(CONTEXT, [EMPTY])
    assert any(r["rule"] == "no_promotion_without_stock" for r in active)


def test_the_retail_rule_is_always_on_when_the_basis_is_retail():
    active = RULES.evaluate(CONTEXT, [])
    assert any(r["rule"] == "retail_not_cost" for r in active)


def test_an_empty_customer_segment_is_flagged_before_a_campaign():
    active = RULES.evaluate(CONTEXT, [], segments={"At Risk": {"count": 0}})
    rule = next(r for r in active if r["rule"] == "check_segments_before_promotions")
    assert "At Risk" in rule["applies_to"]


def test_rules_name_the_products_they_apply_to():
    """
    A rule stated in the abstract is easy for a model to reason past. A rule
    naming Tito's with 1.8 weeks left is not.
    """
    block = RULES.as_prompt_block(RULES.evaluate(CONTEXT, [FAST, HEAVY]))
    assert "Titos 1.75L" in block
    assert "Slow Cognac" in block


def test_the_rules_block_declares_that_it_overrides_everything():
    block = RULES.as_prompt_block(RULES.evaluate(CONTEXT, [FAST]))
    assert "override" in block.lower()


def test_every_rule_explains_itself():
    for rule in RULES.CATALOGUE:
        assert len(rule.why) > 40, rule.key


def test_no_rules_and_no_products_still_produces_a_valid_block():
    assert isinstance(RULES.as_prompt_block([]), str)


# ── Benchmarks ───────────────────────────────────────────────────────────────

def test_turnover_is_interpreted_not_just_reported():
    reading = BENCH.interpret("inventory_turnover", 2.46)
    assert reading["band"] == "needs attention"
    assert "4–6x" in reading["healthy_range"]


@pytest.mark.parametrize("value,band", [
    (7.0, "excellent"), (5.0, "healthy"), (3.0, "needs attention"), (1.0, "high risk"),
])
def test_turnover_bands(value, band):
    assert BENCH.interpret("inventory_turnover", value)["band"] == band


def test_every_benchmark_says_it_is_an_industry_figure():
    """The Phase 22 lesson: an assumption presented as fact costs trust."""
    reading = BENCH.interpret("business_health", 39.4)
    assert "not this store" in reading["basis"]


def test_a_missing_value_returns_nothing_rather_than_guessing():
    assert BENCH.interpret("inventory_turnover", None) is None
    assert BENCH.interpret("not_a_metric", 5) is None


def test_the_benchmark_block_labels_itself_as_industry_data():
    block = BENCH.as_prompt_block(CONTEXT)
    assert "NOT measurements of this shop" in block


# ── Assembly and priority ────────────────────────────────────────────────────

def test_the_prompt_block_states_the_source_priority():
    from app.services.knowledge import service as KNOWLEDGE
    block = KNOWLEDGE._assemble(
        RETRIEVER.search("Should I take this supplier deal?", k=3),
        RULES.evaluate(CONTEXT, [FAST]), CONTEXT)
    assert "SOURCE PRIORITY" in block
    # Rules must appear before the playbooks they outrank.
    assert block.index("BUSINESS RULES") < block.index("LIQUORIQ PLAYBOOK")


def test_the_playbook_block_forbids_using_knowledge_as_a_source_of_figures():
    from app.services.knowledge import service as KNOWLEDGE
    block = KNOWLEDGE._assemble(RETRIEVER.search("inventory", k=2), [], CONTEXT)
    assert "never as a source of figures" in block


def test_citations_are_recorded_for_both_playbooks_and_rules():
    from app.services.knowledge import service as KNOWLEDGE
    cites = KNOWLEDGE._citations(
        RETRIEVER.search("supplier deal", k=2), RULES.evaluate(CONTEXT, [FAST]))
    kinds = {c["kind"] for c in cites}
    assert kinds == {"playbook", "rule"}


def test_the_catalogue_lists_every_playbook():
    from app.services.knowledge import service as KNOWLEDGE
    assert len(KNOWLEDGE.catalogue()) == len({c.doc_id for c in CHUNKS})
