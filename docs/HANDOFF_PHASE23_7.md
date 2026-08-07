# Phase 23.7 — Unified Campaign Workspace

**Status:** spine complete, three sections deferred · 581 tests passing (17 new) · build clean
**Migration head:** `d5a1f39c8b02`
**No new GPT calls. No BI calculation touched.**

---

## 1. Scope — read this first

This phase as specified is several days of work: new persistence, an embedded Label Studio, a ZIP/PDF packager, six asset sections, campaign history, plus the scheduler.

**I built the spine and three sections. I did not build the other three.** Listing them as done would be the more comfortable choice and the wrong one — you would find out by clicking.

| Asked for | Status |
|---|---|
| Campaign Workspace page | ✅ built |
| Campaign Overview | ✅ built |
| Campaign Progress | ✅ built — computed, not stored |
| Scheduler + DB persistence | ✅ built (preparation only) |
| Social / Email / SMS copy — preview, edit, save | ✅ built |
| AI Coach panel | ✅ built, deterministic |
| Campaign history (API) | ✅ built |
| **Advertisement section (inline generate/regenerate)** | ⛔ **links out to `/creative`** |
| **Embedded Label Studio** | ⛔ **links out to `/labels`** |
| **Download Campaign Package (ZIP + PDF)** | ⛔ **not built** |

The two "links out" are honest gaps, not stubs: the pipeline rail carries the strategy into each tool, so the workflow is continuous — but the ad and labels are not rendered *inside* the workspace.

---

## 2. Architecture

```
        AIStrategyReport  (the campaign's brief)
                 │
                 ├── CampaignContext   ← Phase 23.6, derived, stateless
                 │     what every tool should prefill
                 │
                 └── CampaignWorkspace ← Phase 23.7, persisted, stateful
                       status · schedule · copy overrides

                              ↓
                   build_state() composes both
                              ↓
        /campaign/:strategyId  →  Ad Creator · Label Studio · ROI
```

**Two objects, deliberately.** `CampaignContext` is *derived and stateless* — what a tool should prefill. `CampaignWorkspace` is *persisted and stateful* — what the owner decided. Merging them would mean either persisting derived values (which then go stale when the strategy changes) or recomputing intent on every load (which is impossible — intent isn't derivable).

### The decision worth defending: progress is computed, never stored

The obvious design is `ad_done`, `labels_done`, `sms_done`, set by whichever page finished the work. It drifts. Delete a creative and the flag stays true. Make a label outside the workspace and the flag stays false. The owner then sees a progress bar disagreeing with his own assets — worse than no progress bar.

So each step **reports itself by reading the real asset**: the ad step queries `ad_creatives`, labels query `label_designs`, ROI queries `campaigns`. Nothing to keep in sync because nothing is duplicated. Two tests enforce it by reading the model's source and failing if a `_done` flag or any asset content appears.

The only stored state is **intent** — status, schedule, copy overrides — because nothing else records it.

---

## 3. Files

**New**
| File | Purpose |
|---|---|
| `models/campaign_workspace.py` | status, schedule, copy overrides. No flags, no asset content |
| `services/campaign_workspace.py` | state assembly, computed progress, schedule resolution, coach line |
| `routes/workspace.py` | 5 endpoints |
| `alembic/versions/d5a1f39c8b02_campaign_workspaces.py` | migration |
| `pages/CampaignWorkspace.jsx` | the page |
| `tests/test_campaign_workspace.py` | 17 tests |

**Modified:** `main.py` · `models/__init__.py` · `App.jsx` · `api/client.js` · `vite.config.js`

---

## 4. API

| Method | Path | Purpose |
|---|---|---|
| GET | `/workspace` | campaign history |
| GET | `/workspace/{strategy_id}` | the whole workspace — created on first visit |
| PATCH | `/workspace/{strategy_id}/schedule` | choose the window |
| PATCH | `/workspace/{strategy_id}/status` | move through the lifecycle |
| PATCH | `/workspace/{strategy_id}/copy` | save a copy edit |

Workspaces are created **lazily**. Most strategies are read and never executed; a table of empty workspaces would be noise in the history the owner scans.

---

## 5. Two design details

**Copy edits are overrides, not overwrites.** They live in `copy_overrides` keyed by channel. The AI's original stays auditable, and a regretted edit is undone by clearing one key rather than regenerating the campaign. Saving empty text reverts to the original.

**Scheduling is preparation and says so, on screen and in the API response.** *"This records your plan. Sending is not automated yet — you will still launch it yourself."* An owner who believes he has scheduled an SMS that never sends has been failed in the worst way a product can fail someone.

Presets resolve to real datetimes **server-side**, so "Friday evening" means the same thing on any device — and a worker reading these rows later never has to interpret it. Scheduling "Friday evening" *on* a Friday rolls to next week: he's planning, not panicking.

---

## 6. Commands

```bash
cd ~/Desktop/LiquorIQ/backend && source venv/bin/activate
alembic upgrade head              # → d5a1f39c8b02
pytest -q                         # 581 passed
uvicorn app.main:app --reload

cd ../frontend && npm run dev
```

---

## 7. Testing checklist

- [ ] `alembic upgrade head`, restart uvicorn
- [ ] Open `/campaign/<strategy_id>` → overview, progress, copy, scheduler
- [ ] Progress shows Strategy ✓ and everything else per your real assets
- [ ] Click **Advertisement** in the rail → `/creative?strategy=<id>`, pre-filled
- [ ] Generate an ad, return → the Advertisement step is now ✓ (computed, not flagged)
- [ ] Edit the SMS copy → Save edit → reload → the edit persists
- [ ] Clear an edit and save → reverts to the AI original
- [ ] Choose **Friday evening** → confirmation with a real date; status → scheduled
- [ ] `GET /workspace` lists the campaign
- [ ] `pytest -q` → 581

---

## 8. Git commit

```bash
git add -A
git commit -m "feat(workspace): Phase 23.7 — Campaign Workspace spine" \
  -m "A campaign becomes a project: one page with overview, computed progress,
editable channel copy, and a scheduler. The tools were never the problem — the
owner had to hold the pipeline in his head and navigate it from a sidebar." \
  -m "PROGRESS IS COMPUTED, NEVER STORED. Each step reports itself by reading
the real asset. Done-flags drift: delete a creative and the flag stays true,
and a progress bar disagreeing with the owner's own assets is worse than none.
Two tests read the model source and fail if a flag or asset content appears." \
  -m "Two objects on purpose: CampaignContext is derived and stateless (what a
tool should prefill), CampaignWorkspace is persisted and stateful (what the
owner decided). Merging them would either persist values that go stale or try
to recompute intent, which is not derivable." \
  -m "Copy edits are overrides, not overwrites — the AI original stays
auditable. Scheduling is preparation and says so on screen and in the API." \
  -m "NOT built: inline ad generation, embedded Label Studio, campaign package
download. Those sections link out. Migration d5a1f39c8b02. 581 tests passing."
```

---

## 9. What is genuinely missing

1. **Inline ad generation** — the section links to `/creative`. Embedding means lifting generation state out of `Creative.jsx` into a shared hook.
2. **Embedded Label Studio** — it is a large canvas editor with its own state machine. Embedding it is a phase.
3. **Download Campaign Package** — needs a ZIP builder plus a summary PDF. The `pdf` skill and the existing label PDF renderer are the route in.
4. **Labels progress is a weak signal.** `label_designs` has no `strategy_id`, so the step reports whether the shop has *any* saved label. Flagged `weak: true` in the payload rather than dressed up. **Fixing this needs a migration adding `strategy_id` to `label_designs`** — worth doing before the embed.
5. **Nothing executes a schedule.** No worker reads `scheduled_for`.

---

## 10. Interview notes

**"Why compute progress instead of storing it?"**
Because stored flags need an owner, and no single page owns them. Delete a creative and the flag stays true. The failure is silent and it destroys trust in the one widget whose entire job is telling you the truth about your own work. Reading the assets costs a few queries and can never be wrong.

**"Why two objects instead of one campaign model?"**
They have different lifetimes. Context is derived from the strategy and must change when the strategy does. Workspace is intent and must survive regardless. Persisting the context would make prefills go stale; deriving the workspace is impossible, because you cannot derive what someone decided.

**"You didn't finish the phase."**
Correct, and I'd rather say so than list six sections as done and let you find out by clicking. The spine is the part that's hard to change later — the model, the computed-progress decision, the two-object split. The three missing sections plug into it without touching any of that, which is what "future ready" actually has to mean.
