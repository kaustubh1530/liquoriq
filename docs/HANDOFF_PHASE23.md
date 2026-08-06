# Phase 23 — AI Business Advisor

**Status:** complete · 456 backend tests passing (32 new) · frontend build clean · 0 lint errors
**Migration head:** `c4e8b2f713a9`
**Flagship feature.** This is the thing that makes LiquorIQ an operating system rather than a dashboard.

---

## 1. The architectural decision that defines this phase

The brief said *"collect ALL context before every answer"*. **I did not build it that way, and the reason is the whole design.**

This store has 1,393 products, 466 slow movers, seven opportunity types, a customer file and a campaign history. Serialising all of it into every prompt is roughly **80,000 tokens per question**: slow, expensive on every message, and — the part that actually matters — **it produces worse answers**. A model handed everything attends to nothing in particular. The one figure that answers the question gets the same weight as the 1,392 that don't.

So the design is a split:

| | What | Size | When |
|---|---|---|---|
| **Base context** | Store profile, health score + components, headline KPIs, stock-class counts, top 3 actions, period metadata | ~1 KB | Always |
| **Tools** | Inventory, categories, action centre, reorder list, customers, campaigns, strategies, holidays, deals, trend, product lookup | On demand | When the model asks |

*"Why are tequila sales down?"* pulls category intelligence, then — having seen the answer — pulls the product list for that category. **That second call is a decision made with information the model did not have when it started.** That is what makes it an agent rather than a prompt with a large attachment, and it is what the brief's own TOOLS section describes.

It also delivers the explainability requirement for free. We don't *ask* the model which data it used — we record which tools ran. A claimed citation and an observed one are very different guarantees.

---

## 2. Architecture

```
    owner's question + conversation memory
                    ↓
        base context (1 KB, always present)
                    ↓
    ┌────────── GPT-4o ──────────────────────────┐
    │  wants a tool?  → execute → feed result back│  ← up to 4 rounds
    │  no more tools? → final structured answer    │
    └──────────────────────────────────────────────┘
                    ↓
    answer + the tools that ACTUALLY RAN
                    ↓
    persisted: message + tools_used (audit trail)
```

**Module boundaries, and why:**

| Module | Responsibility | Why separate |
|---|---|---|
| `context.py` | Assemble base context from `build_intelligence()` | One place that decides what's "always known" |
| `tools.py` | 11 tools, each a thin adapter over an existing service | Registry pattern — adding a tool is one dict entry |
| `prompt.py` | Identity, rules, response contract | Prompt is content, not code; changes without touching logic |
| `agent.py` | The loop, memory, tool dispatch, degradation | **Zero OpenAI imports** — fully testable |
| `openai_agent.py` | The only SDK contact; normalises the reply shape | Swap providers by editing one file |

`agent.py` having no SDK import is deliberate: it means the entire agent loop is tested with a three-line fake caller, no API key, no network.

---

## 3. Files

### Created — backend

| File | Purpose |
|---|---|
| `services/advisor/context.py` | Base context assembly |
| `services/advisor/tools.py` | 11-tool registry + OpenAI schema + safe executor |
| `services/advisor/prompt.py` | System prompt, response contract, brief prompt |
| `services/advisor/agent.py` | Agent loop, memory, deterministic fallback |
| `services/advisor/openai_agent.py` | The only OpenAI touchpoint |
| `models/advisor_conversation.py` | `AdvisorConversation` + `AdvisorMessage` |
| `alembic/versions/c4e8b2f713a9_advisor_conversations.py` | Migration |
| `routes/advisor.py` | 7 endpoints |
| `tests/test_advisor_agent.py` | 32 tests |

### Created — frontend

| File | Purpose |
|---|---|
| `pages/AIAdvisor.jsx` | Brief, conversation, suggestions, history, sources, quick actions |

### Modified

`app/main.py` (router) · `app/models/__init__.py` · `api/client.js` (`advisorApi`) · `vite.config.js` (`/advisor` proxy) · `App.jsx` (route) · `Layout.jsx` (nav — AI Advisor sits **second**, under Dashboard)

### Not touched

Every Phase 22 calculation. No BI service, model or endpoint was modified. **456 tests passing is the proof.**

---

## 4. The eleven tools

| Tool | Wraps | Answers |
|---|---|---|
| `inventory_intelligence` | `build_intelligence()` | "What's not selling?" "What's sold out?" |
| `category_intelligence` | `build_intelligence()` | "Why are tequila sales down?" |
| `action_center` | `build_intelligence()` | "What should I do?" "Where am I losing money?" |
| `reorder_list` | `bi.reorder` | "What should I reorder first?" |
| `customer_segments` | `customer_service.segment_summary` | "Who should I text?" |
| `campaign_performance` | `campaign_service` | "Did my last campaign work?" |
| `ai_strategies` | `AIStrategyReport` | "What have you already suggested?" |
| `upcoming_holidays` | `holiday_calendar` + `bi.seasonality` | "What should I plan for?" |
| `supplier_deals` | `deal_service.list_deals` | "Should I take this deal?" |
| `revenue_trend` | `analytics_service.get_sales_trend` | "Are sales up or down?" |
| `product_lookup` | `build_intelligence()` | "How is Casamigos doing?" |

**No tool calculates anything.** There's a test that reads each tool's source and fails if it finds `*`, `/`, `sum(` or `round(`. Two sources of truth for one figure is how the advisor ends up contradicting the dashboard.

---

## 5. Swagger endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/advisor/brief` | Today's proactive briefing |
| GET | `/advisor/suggestions` | Opening question cards |
| GET | `/advisor/context` | **Transparency** — everything the advisor knows + its tools |
| POST | `/advisor/ask` | Ask a question; continues a thread |
| GET | `/advisor/conversations` | Thread list |
| GET | `/advisor/conversations/{id}` | One thread with messages + sources |
| DELETE | `/advisor/conversations/{id}` | Delete a thread |

`/advisor/context` exists because an advisor whose knowledge is a black box is one you have to take on faith.

---

## 6. Guardrails

**Never hallucinate.** Four layers:

1. The prompt forbids invention explicitly, with the required decline phrase: *"I don't have enough information."*
2. Every figure must come from base context or a tool result.
3. `tools_used` is recorded from execution, not claimed.
4. The prompt carries the Phase 22 lesson forward: inventory figures are **retail, not cash**, unless the basis says cost.

**Never go dark.** Every failure path returns something useful:

| Failure | Result |
|---|---|
| One tool throws | `{"error": ...}` → advisor answers about what did work |
| Unknown tool name | Error string, loop continues |
| Bad tool arguments | Named error, loop continues |
| OpenAI down / out of credit | `FALLBACK` pointing at the dashboard |
| Brief generation fails | `_deterministic_brief()` — real numbers, no AI |
| Model loops forever | Capped at 4 rounds, final call made with `tools=None` |

---

## 7. Memory

Persisted server-side, not in the browser:

- He closes the tab mid-service and expects the thread to survive
- `tools_used` is an audit trail — a client-held history can be edited, and history is an input to a system that spends money
- Capped at `MEMORY_TURNS = 8` so conversation never crowds out store data

Store context is injected as a **system** message, not appended to the question — it's standing knowledge, not something the owner said, and models weight the two differently.

---

## 8. Terminal commands

```bash
cd ~/Desktop/LiquorIQ/backend
source venv/bin/activate
alembic upgrade head              # → c4e8b2f713a9
pytest -q                         # 456 passed
uvicorn app.main:app --reload     # MUST run from backend/

cd ../frontend && npm run dev
```

---

## 9. Testing steps

**Automated (no API key needed):**
```bash
pytest tests/test_advisor_agent.py -v   # 32 tests, entire loop, zero network
```

**Manual:**

- [ ] `alembic upgrade head`, restart uvicorn
- [ ] Open **AI Advisor** — the brief appears without you typing
- [ ] Ask *"Why are tequila sales down?"* → answer cites Category performance
- [ ] Expand **Business data used** → tools listed with green ticks
- [ ] Ask *"I'm thinking about Labor Day"*, then *"What should I promote?"* → **the second answer knows it's still about Labor Day**
- [ ] Ask *"How many customers do I have in Ohio?"* → *"I don't have enough information."*
- [ ] Ask *"What should I reorder first?"* → names real products with quantities
- [ ] New conversation → history sidebar shows both; reopening restores messages
- [ ] Unset `OPENAI_API_KEY`, restart → brief still renders with real figures, labelled "without AI"
- [ ] `/docs` → all 7 endpoints under **AI Business Advisor**

---

## 10. Git commit

```bash
cd ~/Desktop/LiquorIQ
git add -A
git commit -m "feat(advisor): Phase 23 — agentic AI Business Advisor" \
  -m "An agent, not a chatbot. GPT-4o receives a 1KB base context and eleven
tools over the existing deterministic services, and chooses which to call for
each question. Multi-round: it can look at categories, see the answer, and then
pull the products inside the worst one — a decision made with information it did
not have when it started." \
  -m "Deliberately NOT full-context stuffing. Serialising 1,393 products into
every prompt would be ~80k tokens per question: slow, expensive, and worse —
a model given everything attends to nothing in particular." \
  -m "Explainability is observed, not claimed: tools_used records what actually
executed, persisted with each message as an audit trail." \
  -m "agent.py has zero OpenAI imports — the SDK lives in openai_agent.py, so
all 32 tests run the full loop with a fake caller, no key and no network." \
  -m "Degrades everywhere: a failed tool returns an error string, an unreachable
model returns deterministic prose written from the same figures. The brief is
never blank." \
  -m "New: services/advisor/{context,tools,prompt,agent,openai_agent}.py,
models/advisor_conversation.py, routes/advisor.py (7 endpoints),
pages/AIAdvisor.jsx. Migration c4e8b2f713a9." \
  -m "NO CHANGES to any Phase 22 calculation. 456 tests passing."

git push
```

---

## 11. Known limitations

1. **Cost per question is unbounded** — 4 tool rounds means up to 5 API calls. No per-store rate limit yet; a bored owner could run up a bill.
2. **No caching between questions.** Asking two things in a row re-runs `build_intelligence()` each time. The brief mentioned "load context once, cache intelligently" — I did not build the cache because invalidating it correctly (on upload, on parse, on margin change) is its own piece of work and a stale advisor is worse than a slow one. **This is the first thing I'd do next.**
3. **No streaming.** Answers appear all at once after 3–8 seconds. Streaming is a real UX improvement and a real chunk of work.
4. **Tool results truncated at 12,000 characters.** A pathological question could lose data silently.
5. **Advice quality is unmeasured.** The tests prove the loop works; nothing proves the recommendations are *good*. That needs a rubric and human review over months.

---

## 12. Interview explanation

**"What makes this agentic rather than a chatbot?"**
Three things. It chooses its own data sources from eleven tools rather than receiving a fixed payload. It loops — a second tool call informed by the first result is a decision, not a script. And it acts before being asked: the page opens with a briefing the owner didn't request.

**"Why not send all the context?"**
Because 80,000 tokens of context makes the answer worse, not just slower. Attention is finite; the one number that matters gets diluted by 1,392 that don't. Tool calling is retrieval with the model doing the selecting, which is exactly what it's good at.

**"How do you know it isn't making things up?"**
Layered. The prompt forbids it. The figures come from tools over deterministic services. And critically, the citation list is built from *executed* tool calls — I don't ask the model what it consulted, I record it. Phase 22 taught me that a model's account of its own reasoning isn't evidence.

**"How is it testable without an API key?"**
The OpenAI client is injected. `agent.py` imports nothing from the SDK; `openai_agent.py` is the only file that does, and it normalises the response into a plain dict. All 32 tests drive the real loop with a fake caller — including multi-round reasoning, the round cap, tool failure, and model outage.

**"What happens when OpenAI is down?"**
The brief renders from `_deterministic_brief()` using the same figures, labelled as written without AI. Questions get an honest message pointing at the dashboard, which is entirely AI-free. The product degrades to "quieter", never to "broken".

**"What would you build next?"**
Context caching keyed on the latest upload id, with invalidation on parse and on margin change. It's the obvious performance win and I left it out on purpose — a cache that serves stale numbers to a business advisor is worse than a slow one, and doing it properly is its own phase.
