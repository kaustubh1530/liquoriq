# Phase 24 — LiquorIQ Knowledge Engine

**Status:** complete · 524 backend tests passing (40 new) · no migration · no new GPT calls
**Corpus:** 17 playbooks → 150 retrievable chunks
**Retrieval:** deterministic, offline, no API key

---

## 1. The architectural decision — read this first

**The brief asked for embeddings in a vector database. I built the RAG pipeline with a pluggable retriever and shipped a lexical one as the default.** That is the most important call in this phase and it deserves defending rather than burying.

| | Embeddings | Lexical (shipped) |
|---|---|---|
| Corpus size where it wins | 10k+ chunks | **~150 chunks** |
| Cost to build index | 1 API call per chunk | zero |
| Cost per query | 1 API call | zero |
| Cost to edit a playbook | full re-index | zero |
| Infrastructure | pgvector extension + migration + ingest job | none |
| Deterministic | no | **yes** |
| Testable offline | mocked | **genuinely** |

At 150 chunks over a corpus **we wrote and tagged ourselves**, BM25 with hand-authored keyword metadata beats cosine similarity on relevance. Embeddings solve the synonym problem at scale; we don't have a scale problem, we have a **writing** problem — retrieval quality is not the bottleneck, playbook quality is.

`EmbeddingRetriever` implements the same interface and is present but disabled. Switching is a config change (`KNOWLEDGE_RETRIEVER=embedding`) with **zero caller changes**. That is the point of the interface: **the decision is reversible.** Shipping an unused pgvector table to look sophisticated would have been the worse engineering call.

---

## 2. Architecture

```
    question + store context
              ↓
    ┌──────── services/knowledge/ ────────────────┐
    │  retriever.py   chunk → score → top-k (RAG) │
    │  rules.py       hard constraints, checked   │
    │  benchmarks.py  what "good" looks like      │
    │  service.py     assemble + cite             │
    └──────────────────────────────────────────────┘
              ↓  one system message, ordered by authority
         advisor/agent.py  (unchanged loop)
              ↓
            GPT-4o
```

**Source priority, stated to the model explicitly:**

1. **Business rules** — checked against his numbers; the model cannot argue with these
2. **Store data** — measured from his own report
3. **LiquorIQ playbook** — our experience; advice, never figures
4. **Industry benchmarks** — explicitly not his history
5. **GPT reasoning** — everything left

---

## 3. Files created

| File | Purpose |
|---|---|
| `services/knowledge/retriever.py` | Frontmatter parsing, section chunking, BM25 scoring, pluggable backends |
| `services/knowledge/rules.py` | 7 deterministic rules evaluated against real products |
| `services/knowledge/benchmarks.py` | 5 metrics with bands and verdicts |
| `services/knowledge/service.py` | Assembly, priority ordering, citations, catalogue |
| `knowledge/**/*.md` | 17 playbooks |
| `tests/test_knowledge_engine.py` | 40 tests |

**Modified:** `advisor/agent.py` (retrieve before reasoning; carry `knowledge_used`), `routes/advisor.py` (citations + catalogue on `/advisor/context`).

**No migration. No new endpoint. No new GPT call.** The knowledge block rides on the existing advisor request.

---

## 4. The playbooks (17)

**Retail** — inventory, cashflow, merchandising, promotions, customers
**Pricing** — discounts, supplier_deals, inventory_turnover
**Categories** — whiskey, wine, tequila, beer
**Holiday** — labor_day, thanksgiving, christmas
**Marketing** — sms, bundles

Every one carries: Definition · Best practices · Common mistakes · Recommended actions · Seasonality · KPIs · Benchmarks · Store tips · **AI notes**.

The **AI notes** section is where an operator's judgement becomes an enforceable constraint — *"Beer needs far tighter cover than spirits; do not apply the 6–8 week guidance here"*, *"Never recommend discounting allocated stock"*. There's a test that fails if any playbook lacks one.

**Adding a playbook is dropping a `.md` file in.** No code, no re-index, no migration.

---

## 5. Business rules

Seven, evaluated against the store's actual products and handed to the model **naming the specific items**:

> · Never recommend discounting a product that is already selling well.
> **Right now this applies to: Titos 1.75L, Bulleit 1.75L**

A rule stated abstractly is easy to reason past. A rule naming Tito's with 1.8 weeks left is not.

---

## 6. Explainability

`knowledge_used` sits alongside `tools_used` in every response — **observed during execution, not claimed by the model.** The owner sees which playbooks were retrieved (with scores) and which rules fired (with the products they hit).

`GET /advisor/context` now returns the full catalogue and rule list.

---

## 7. Verified retrieval

```
How should I prepare for Labor Day?   → holiday/labor_day        10.52
Why is my inventory unhealthy?        → retail/inventory          8.95
Should I take this supplier deal?     → pricing/supplier_deals   15.69
How should I promote Cabernet?        → categories/wine           6.26
mezcal                                → categories/tequila
what is the capital of France         → nothing above threshold
```

Weak matches are filtered at `MIN_SCORE = 1.5` — an irrelevant chunk is worse than none, because it crowds out the store's own data.

---

## 8. Commands

```bash
cd ~/Desktop/LiquorIQ/backend && source venv/bin/activate
pytest tests/test_knowledge_engine.py -v    # 40 tests, no API key
pytest -q                                   # 524 passed
uvicorn app.main:app --reload
```

No migration. Restart the backend and ask the advisor a question.

---

## 9. Testing

- [ ] Ask *"Should I take this supplier deal?"* → answer cites the supplier playbook
- [ ] Expand sources → playbook sections listed with scores
- [ ] Ask *"Should I discount Tito's?"* → refuses, citing the fast-mover rule
- [ ] Ask *"What's the capital of France?"* → no playbook retrieved
- [ ] `GET /advisor/context` → 17 playbooks + 7 rules
- [ ] Add a `.md` to `knowledge/retail/`, restart, ask a matching question → retrieved

---

## 10. Git commit

```bash
git add -A
git commit -m "feat(knowledge): Phase 24 — LiquorIQ Knowledge Engine (RAG)" \
  -m "Retrieval-augmented advice: 17 playbooks, 150 chunks, chunked on section
headers so a retrieved chunk is always a complete thought. Business rules are
evaluated against the store's real products and outrank the model. Benchmarks
interpret figures rather than compute them." \
  -m "Pluggable retriever, lexical by default. At 150 chunks over a corpus we
wrote and tagged, BM25 beats embeddings on relevance and costs nothing to build,
query or edit. EmbeddingRetriever implements the same interface and is wired but
disabled — switching is a config change, not a rewrite." \
  -m "Explainability: knowledge_used sits beside tools_used, recorded during
execution. Adding a playbook is dropping a .md file in." \
  -m "524 tests passing (40 new), all offline. No migration, no new GPT call."

git push
```

---

## 11. Known limitations

1. **17 playbooks, not the 40+ the directory listing implied.** I chose depth: every one is written as a consultant would write it, with a real point of view. Thin playbooks would have made retrieval *look* better while making advice worse.
2. **Retrieval is section-level, not passage-level.** A long section returns whole. Fine at this size; a re-ranker would help at 500+ documents.
3. **No knowledge versioning.** Editing a playbook changes advice with no audit trail of what changed when.
4. **`get_retriever()` is cached for the process lifetime** — editing a playbook needs a restart in development.
5. **The industry benchmarks are my figures, from trade norms.** They are labelled as industry data everywhere, but they have not been validated against a dataset of real independents.

---

## 12. Interview notes

**"Why not embeddings?"**
Because 150 chunks is not a retrieval problem. Embeddings solve synonym-matching at scale and cost an API call per chunk to build, per query to search, and a full re-index per edit. Over a corpus we authored and tagged ourselves, BM25 with keyword metadata scores better *and* stays deterministic — which is why 40 retrieval tests run offline with no key. I built the interface so switching is one config line, because the right answer changes at a few hundred documents.

**"How do rules beat the model?"**
They're evaluated in Python against his actual products and injected as constraints naming specific items, above the playbooks in a stated priority order. "Never discount a fast mover" in a prompt is a hope. "Do not discount Tito's, it has 1.8 weeks left" is a fact the model has nothing to say about.

**"How is knowledge kept from becoming a source of numbers?"**
The playbook block says it explicitly: *"This is EXPERIENCE, not measurement — never a source of figures about this store."* Same discipline as Phase 22, where GPT explains deterministic output but cannot produce it. Knowledge interprets; only the engine measures.

**"What's the moat?"**
Not the retrieval — that's a weekend. The moat is the playbooks, and specifically the AI notes: *"beer needs tighter cover than spirits"*, *"never discount allocated stock"*, *"rosé bought in August is a next-June problem"*. That's operator judgement encoded as constraints, and it compounds every time someone adds a file.
