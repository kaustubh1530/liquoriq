# Phase 22 — Business Intelligence Engine

**Status:** complete · 424 backend tests passing · frontend build clean
**Migration head:** `b8f4c2a91d7e`
**Validation:** [`VALIDATION_JULY_2026.md`](./VALIDATION_JULY_2026.md) — every metric, its formula, its confidence, its limitations

---

## 1. What this phase did

Turned an analytics dashboard into a business decision platform, and then spent
as long again making its numbers defensible.

The engine reads a POS export and answers one question: **what should the owner
do this week, and what is it worth?** Every figure is computed deterministically
in Python. GPT is used in exactly one place — to explain a finished number in
plain English — and is structurally prevented from producing a figure of its own.

### The architectural spine

```
POS file → parser → normalized_sales
                          ↓
      ┌───────────────────────────────────────────┐
      │  services/bi/  — DETERMINISTIC, NO AI     │
      │                                           │
      │  assumptions.py   every rate in one place │
      │  categorizer.py   5-tier category cascade │
      │  product_metrics  9 stock classes, 2 scores│
      │  seasonality.py   which products per holiday│
      │  opportunities.py 7 detectors + allocation│
      │  planning.py      timelines + phased plans│
      │  valuation.py     retail vs cost          │
      │  reorder.py       the purchase list       │
      │  action_center.py priorities + health     │
      │  engine.py        the only DB-touching one│
      └───────────────────────────────────────────┘
                          ↓
                    explain.py  ← the ONLY GPT call
                          ↓
                 /intelligence  → Business Control Center
```

---

## 2. The trust work — six defects found against real data

Every one of these shipped, rendered confidently, and was wrong. They are
listed because the *pattern* matters more than the individual bugs.

### 2.1 The snapshot merged every upload ever (85x overstatement)

`_latest_snapshot` selected every row the store had uploaded and de-duplicated
by product name, merging five reporting periods into one "snapshot". Products
from an old report survived with stock 0 and historical sales, which the engine
correctly read as *"sold out, losing sales"*.

| | Shown | Actual |
|---|---:|---:|
| Products | 2,415 | 1,393 |
| Out of stock | 1,065 | 115 |
| Reorder opportunity | $846,785 | **$9,995** |

The store's entire July revenue was $66,753. The card claimed $211,695/week at
risk — fourteen times total weekly sales.

**Fix:** the snapshot is scoped to one upload, and the period comes from that
same upload so units and days can never come from different files.

### 2.2 Re-uploading a period double-counted it

A monthly summary is a *statement about a period*, not a batch of new sales.
Six uploads of July meant July was counted six times in every store-wide total —
the revenue trend peaked at $220k.

**Fix:** parsing a report supersedes an earlier report covering the same period.
`cleanup_duplicate_uploads.py` clears historical duplicates.

Related: confidence counted *uploads* rather than *distinct periods*, so one
month uploaded six times claimed "velocity confirmed across several uploads".

### 2.3 Retail was labelled as cash

`unit_price` is derived from sales (`total ÷ quantity`) — the **shelf price**.
"Cash frozen $220,661" overstated what the owner spent by his entire margin
(~$154,000 at 30%).

**Fix:** `valuation.py` owns the labelling. Without a margin the dashboard says
*"Slow stock (retail value)"* and shows no cost figure. **No default margin is
assumed** — a number the owner didn't supply is not his number.

### 2.4 Opportunities were summed even though they overlapped

Clearance and Seasonal named the same 18 of 20 products. "$191,074 on the
table" added both. You cannot dump a bottle at 60% clearance *and* sell it at a
holiday markup.

**Fix:** `allocate_exclusively()` gives every product one primary action — the
one that values it most — and recomputes each opportunity from what it kept.
Customer-led opportunities (win-back, campaign repeat) are exempt, since they
don't compete for stock. Yielded products are disclosed on the card, not hidden.

### 2.5 Seasonal scoped 99% of the inventory

"Labor Day · stock in scope $310,591" was essentially the whole shop, times a
flat 15%. Nobody buys Cognac for a barbecue. Worse, the value was 15% of
**stock value**, so hoarding dead inventory *increased* the opportunity.

**Fix:** `seasonality.py` names the categories that move for each holiday, plus
keywords for cases a category can't express (St Patrick's is *Irish* whiskey).
Every qualifying product carries a reason. The value is now a lift on what
those products **actually sold**, capped by stock on hand.

Labor Day now scopes 514 of 1,393 products (36.9%) and values at $5,267 —
20% of the $26,336 those products already sell.

> The validation report caught `CAMEL LIGHTS BOX` qualifying for a barbecue via
> the keyword "light". Tobacco, Snacks and Non-alcoholic are now excluded
> outright. One absurd item on a campaign list discredits the other 500.

### 2.6 "Do this now" on two months of revenue

$132,396 of clearance against a store doing $66,753/month, labelled P1 · Do this
now, with no timeframe.

**Fix:** `planning.py` gives every opportunity a window and a reason, and turns
large clearances into phased plans sized against the store's own revenue. The
capacity assumption (a clearance adds ~15% to a normal month) is stated on the
card, not buried.

---

## 3. The pattern behind the bugs

Five of the six were **two individually-correct values combined without
validating their relationship**:

- correct stock + correct sales, from *different reports*
- correct retail figure + a label that said *cash*
- correct clearance value + correct seasonal value, *added*
- correct price + correct product, *not the same product* (the ad creator bug)
- correct upload count used as *periods of history*

Unit tests cannot catch this class by construction — each module was right on
its own. What catches it is a **contract test at the seam** that builds fixtures
by calling the real producer, plus **an external plausibility check**: any
opportunity larger than the store's revenue is arithmetic, not insight.

The AI guardrail was never the weak point. The engine was strict that GPT may
not invent a number, but had no rule that a *correct* number must be attached to
the right thing. **Provenance matters as much as accuracy.**

---

## 4. Files

### Created

| File | Purpose |
|---|---|
| `services/bi/assumptions.py` | every rate and threshold, with a `why` for each |
| `services/bi/categorizer.py` | 5-tier cascade, 99.2% coverage on real data |
| `services/bi/product_metrics.py` | 9 stock classes, health + opportunity scores |
| `services/bi/opportunities.py` | 7 detectors + exclusive allocation |
| `services/bi/seasonality.py` | holiday → category/keyword relevance rules |
| `services/bi/planning.py` | execution timelines + phased clearance |
| `services/bi/valuation.py` | retail vs cost, and the labels for both |
| `services/bi/reorder.py` | the purchase list, net of stock on hand |
| `services/bi/action_center.py` | priorities, business health, disclosure |
| `services/bi/explain.py` | the only GPT touchpoint |
| `services/bi/engine.py` | orchestration; the only DB-touching module |
| `models/product_category.py` | category cache (tiers 1–2) |
| `routes/intelligence.py` | 10 endpoints |
| `diagnose_bi.py` | stage-by-stage diagnosis against a live DB |
| `validate_bi.py` | the validation report generator |
| `cleanup_duplicate_uploads.py` | removes superseded periods |
| `pages/dashboard/{HealthScore,ActionCard,ReorderPanel,MarginPrompt}.jsx` | UI |
| `components/FromActionBanner.jsx` | "you arrived from a recommendation" |

### Modified

`parsers/adventpos_parser.py` (period preserved) · `parse_service.py`
(supersede duplicates) · `models/uploaded_report.py` · `models/store.py`
(gross margin) · `services/design_plan.py` + `creative_service.py` (ad price
attribution) · `pages/Dashboard.jsx` · `AIStrategy.jsx` · `LabelStudio.jsx` ·
`api/client.js` · `vite.config.js`

### Migrations

`f2b71c8e4a93` report period → `a3d9e51c7f24` product_categories →
`b8f4c2a91d7e` store gross margin **(head)**

---

## 5. Test suite — 424 passing

| File | Covers |
|---|---|
| `test_bi_metrics.py` | 9 classes, both scores, period arithmetic |
| `test_bi_categorizer.py` | the 5-tier cascade |
| `test_bi_opportunities.py` | all 7 detectors |
| `test_bi_explain.py` | **enforcement** — invented figures rejected in every field |
| `test_bi_engine_adapters.py` | module seams; snapshot scoped to one upload |
| `test_bi_reorder.py` | quantities net of stock; no field may imply cost |
| `test_bi_valuation.py` | never assume a margin; label matches basis |
| `test_bi_trust.py` | exclusivity, seasonal relevance, timelines, phasing |
| `test_ad_price_attribution.py` | the price belongs to the bottle on the ad |

---

## 6. Local commands

```bash
cd ~/Desktop/LiquorIQ/backend
source venv/bin/activate
alembic upgrade head                      # → b8f4c2a91d7e
pytest -q                                 # 424 passed
python cleanup_duplicate_uploads.py --apply
python diagnose_bi.py                     # 12 stages against the live DB
python validate_bi.py --md                # the validation report
uvicorn app.main:app --reload             # MUST be run from backend/

cd ../frontend && npm run dev
```

---

## 7. Testing checklist

- [ ] `alembic upgrade head`, restart uvicorn, dashboard loads
- [ ] Header shows one period, not six uploads
- [ ] Inventory cards say **retail** until a margin is entered
- [ ] Enter a 30% margin → "Cash frozen" ≈ $154,463
- [ ] Reorder card ≈ $9,995 / 115 out of stock (not $846,785)
- [ ] "Reorder products" opens the list; CSV downloads; quantities net of stock
- [ ] Every action card shows a timeline and a reason
- [ ] Clearance shows a phased plan, not "Do this now"
- [ ] Labor Day names beer/seltzer/tequila — no Cognac, no cigarettes
- [ ] Seasonal card discloses products moved to a higher-value action
- [ ] "Why?" returns prose; disconnecting OpenAI still returns text
- [ ] Revenue trend peaks near $67k, not $220k

---

## 8. Known limitations

1. **No cost data.** Retail until the owner supplies a margin. A per-category
   margin would be better than one store-wide figure.
2. **One period of history.** Velocity from a single month; a seasonal product
   reads as a trend. Confidence stays MEDIUM until more periods exist.
3. **No basket data.** Bundle attach rates are industry assumptions.
4. **Holiday lifts are industry figures**, not this store's own past holidays.
   Replace once several years of reports exist.
5. **Stock is a snapshot**, not a monthly average, so in-stock rate can miss a
   stock-out resolved mid-month.
6. **54 negative stock counts** — a counting error at the shop. Isolated and
   reported rather than silently zeroed.
7. **Category rules are US-centric** and tuned for a DMV-area store.

---

## 9. Interview notes

**"How do you stop an LLM inventing financial figures?"**
Don't rely on the prompt. The engine computes every number in Python; GPT
receives finished display values and returns prose. Each figure in its response
is tokenised and checked against the figures supplied — anything invented
discards the whole explanation in favour of deterministic text. Unplug OpenAI
and the product still tells the owner what to do.

**"Your tests passed and the number was still wrong. Why?"**
Because unit tests verify a function against its inputs; they say nothing about
whether the inputs describe reality. 304 tests passed while the dashboard showed
an $846,785 opportunity for a store with $66,753/month of revenue. The check
that caught it compared a derived figure against an independent known quantity.
That belongs in the engine, not just in my head.

**"What was the hardest bug?"**
Not the crash — the plausible one. A 500 gets fixed in ten minutes. A
confidently-rendered wrong number survives because nothing complains, and by the
time a customer notices, they've stopped trusting the other twelve panels too.

**"Why one action per product?"**
Because a product can only be done one thing with. Summing clearance and
seasonal presented a *choice* as a *sum*. Allocation also answers the owner's
actual question — "what do I do with this bottle?" — which the sum never did.
