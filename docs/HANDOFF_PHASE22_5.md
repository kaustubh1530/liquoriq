# Phase 22.5 — Dashboard & Navigation UX Refactor

**Status:** complete · 424 backend tests passing (unchanged) · frontend build clean
**Backend changes:** none. No calculation, model, migration, route or AI call was touched.
**Migration head:** `b8f4c2a91d7e` (unchanged from Phase 22)

---

## 1. The problem

The Dashboard had become an analytics tool wearing a dashboard's clothes. Twelve
panels, all rendered at similar visual weight: health score, four KPI cards,
action centre, inventory bands, category table, growth opportunities, revenue
trend, campaign ROI, assumptions.

Every one of those panels was *correct*. That was the trap — nothing was wrong,
so nothing demanded removal. But a page where everything is important is a page
where the owner does the prioritising, and prioritising is the work the product
exists to do for him.

**A dashboard that is also an analytics tool is neither.** Deciding and
exploring are different modes with different tempos: deciding happens in thirty
seconds standing at the till between customers; exploring happens for twenty
minutes at a desk with a coffee. One page cannot serve both without making the
common case worse.

---

## 2. What changed

### Navigation

```
Dashboard               ← the daily driver
Uploads
Inventory
AI Strategy
AI Ad Creator
Label Studio
Customers
Business Intelligence   ← NEW
Transfers
```

Business Intelligence sits near the bottom deliberately. It is somewhere to
**spend** time, not somewhere to start — placing it high would invite browsing
analytics when the owner came in to do a job.

`/categories` was dropped from the sidebar (Category Intelligence now lives
inside the BI page) but the route remains, linked from BI, so no bookmark breaks.

### Dashboard — five sections, nothing else

| # | Section | Answers |
|---|---|---|
| 1 | Executive hero | "What's this worth?" — greeting, health chip, `+$141,783`, why-chips, CTA, 2–3 sentence brief |
| 2 | AI Business Coach | "What's my biggest problem?" — problem → why it matters → what to do |
| 3 | Business health | "Am I OK?" — score, band, verdict, link to the drivers |
| 4 | Top 3 priorities | "What do I do?" — impact, confidence, action button, Why button |
| 5 | Quick snapshot | Inventory value · Cash frozen · Turnover · Products out of stock |

Four snapshot figures. Not five, not nine.

### Business Intelligence — the analytics workspace

Eight sections with a sticky jump-bar:

1. **Executive metrics** — all five health components, each with its formula, weight, target, and whether the target is an industry benchmark
2. **Revenue trends** — gated at four periods with a progress indicator
3. **Inventory intelligence** — value/frozen/sell-through, plus the clickable bands
4. **Category intelligence** — sortable, expandable, traffic-lit
5. **Growth opportunities** — *all* recommendations, raw and confidence-adjusted totals
6. **Historical performance** — measured campaign lift
7. **Business assumptions** — all nine, each with its `why`
8. **Confidence indicators** — per-opportunity weighting, measured vs estimate, allocation notes

---

## 3. The AI Business Coach — why it is not a GPT call

The card reads conversationally: *"70% of your stock value is sitting in
products that are barely selling. That money can't buy anything else until it
sells. Your stock turns over 2.46× a year against a healthy 4–6×, so it isn't
going to clear on its own."*

Every clause is **selected and phrased from figures the deterministic engine
already returned in the same payload.** No new endpoint, no new model call.

Three reasons:

1. **It sits in the second-most prominent slot on the page.** A round-trip puts
   a spinner there on every load.
2. **It costs money on every page view** for prose that changes only when the
   underlying numbers change.
3. **It cannot contradict the cards beneath it.** An independently-generated
   summary eventually will, and the first time it does, the owner stops
   trusting both.

Per-action AI explanation still exists behind the **Why?** button, where the
latency is opt-in and the response is validated token-by-token against the
figures supplied — the Phase 22 enforcement is untouched.

---

## 4. Files

### Created

| File | Purpose |
|---|---|
| `pages/BusinessIntelligence.jsx` | the analytics workspace — 8 sections, jump-bar |

### Modified

| File | Change |
|---|---|
| `pages/Dashboard.jsx` | rewritten to five sections; analytics removed (moved, not deleted) |
| `pages/dashboard/summary.js` | added `coach()` — deterministic problem/why/action |
| `components/Layout.jsx` | nav reordered; `BarChart3` icon; removed unused `Store` import |
| `App.jsx` | `/intelligence` route |

### Untouched

Every file under `backend/`. No calculation, model, migration, endpoint, or
prompt was modified in this phase.

---

## 5. Nothing was removed

| Panel | Was | Now |
|---|---|---|
| Revenue trend | Dashboard | BI § Revenue trends |
| Category intelligence | Dashboard | BI § Category intelligence (+ `/categories`) |
| Inventory health bands | Dashboard | BI § Inventory intelligence (+ `/inventory`) |
| Growth opportunities | Dashboard | BI § Growth opportunities |
| Campaign ROI | Dashboard | BI § Historical performance |
| Assumptions | Dashboard (collapsed) | BI § Business assumptions — expanded, with `why` |
| Confidence detail | inside cards only | BI § Confidence indicators |
| Health components | not shown | BI § Executive metrics — with formulas |

Two panels are **more** visible than before: assumptions now show their
reasoning, and confidence weighting has a section of its own.

---

## 6. Testing checklist

- [ ] Dashboard shows exactly five sections; readable in under 30 seconds
- [ ] Hero shows greeting, health chip, `+$` figure, three why-chips, both CTAs
- [ ] Coach card names a problem, explains it, recommends an action with a timeline
- [ ] Exactly three priority cards; "All N recommendations →" goes to BI
- [ ] Quick snapshot shows exactly four figures
- [ ] Sidebar matches the nine-item order above
- [ ] `/intelligence` loads; jump-bar scrolls to each of the eight sections
- [ ] Executive metrics shows a formula under every component
- [ ] Trend shows the `1 of 4 reports` progress bar, not an empty chart
- [ ] Inventory bands click through to `/inventory?class=…` pre-filtered
- [ ] Assumptions list all nine with their `why`
- [ ] Confidence section shows raw → adjusted for each opportunity
- [ ] Margin prompt still saves and re-labels the cards
- [ ] `pytest -q` → 424 passed (proves the backend was untouched)

---

## 7. Known issues

1. **ESLint `set-state-in-effect`** fires on 13 files across the codebase,
   including pages never touched in this phase (`Uploads`, `Customers`,
   `AIStrategy`). Pre-existing pattern, not a regression. Worth a dedicated
   cleanup pass.
2. **Bundle is 806 kB** (237 kB gzipped) and growing. Recharts and react-konva
   dominate. Route-level code splitting would take a meaningful bite —
   `/labels` and `/intelligence` are the obvious first splits.
3. **Mobile is untested in a real browser.** Layouts use responsive utilities
   and the build is clean, but nobody has held a phone.
4. **The coach only distinguishes two problem shapes** (slow stock vs
   stock-outs). A third — margin erosion — needs cost data, which the POS
   export doesn't carry.

---

## 8. Git commit

```bash
cd ~/Desktop/LiquorIQ
git add -A
git commit -m "refactor(ux): Phase 22.5 — split decision-making from analysis" \
  -m "The Dashboard had twelve panels of near-equal weight. Every one was
correct, which is why none demanded removal — but a page where everything is
important makes the owner do the prioritising, and that is the work the product
exists to do for him." \
  -m "Dashboard is now five sections: executive hero, AI Business Coach,
business health, top 3 priorities, quick snapshot. Readable in under 30
seconds." \
  -m "New Business Intelligence page (/intelligence) holds everything
analytical in eight sections: executive metrics with formulas, revenue trends,
inventory intelligence, category intelligence, all growth opportunities,
historical performance, business assumptions, confidence indicators. Nothing
was deleted — assumptions and confidence detail are MORE visible than before." \
  -m "The AI Business Coach is deterministic: every clause is selected from
figures already in the payload. No new GPT call, so it cannot contradict the
cards beneath it, costs nothing per page view, and never renders a spinner in
the second-most prominent slot on the page." \
  -m "Sidebar reordered by frequency of use. Business Intelligence sits low on
purpose: somewhere to spend time, not somewhere to start." \
  -m "NO BACKEND CHANGES. 424 tests still passing, which is the proof."

git push
```

---

## 9. Interview notes

**"How do you decide what to remove from a dashboard?"**
You don't remove by correctness — everything on that page was correct. You
remove by *mode*. Ask what question each panel answers and how long the user
has to answer it. Anything that takes twenty minutes to act on doesn't belong
next to something that takes thirty seconds. Then you move it, never delete it,
and put a link where it used to be.

**"Why fake the AI card instead of calling the model?"**
It isn't fake — it's deterministic. The distinction that matters is that the
figures come from the same payload as the cards below it, so the two can never
disagree. A model call would add latency to the second-most prominent element,
cost money per page view, and introduce a class of bug where the summary
contradicts the evidence. I kept the real model call where it earns its cost:
behind an opt-in "Why?" button, with output validated against supplied figures.

**"What did you not fix?"**
The bundle size and a codebase-wide lint pattern. Both were pre-existing and
neither blocks the user. Fixing them in a UX phase would have made the diff
harder to review for the thing it was actually about.
