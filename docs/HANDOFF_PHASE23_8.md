# Phase 23.8 — Finishing the Campaign Workspace

**Status:** the three deferred sections are built · 614 tests passing (33 new) · build clean
**Migration head:** `e2b74c1a95d3`
**No new GPT calls. No BI calculation touched. No new dependency.**

---

## 1. What 23.7 left, and what happened to it

| Deferred in 23.7 | Now |
|---|---|
| `label_designs` has no `strategy_id` — labels progress is a weak signal | ✅ migration `e2b74c1a95d3`; `weak: true` gone |
| Download Campaign Package (ZIP + PDF) | ✅ `GET /workspace/{id}/package` |
| Advertisement section links out to `/creative` | ✅ embedded, one shared hook |
| Embedded Label Studio | ✅ embedded, one shared editor |

Four commits, in dependency order — the migration first, because the package
needs to know which labels belong in the ZIP and the embedded studio needs to
know what it is showing.

---

## 2. The migration, and why it is nullable

`label_designs.strategy_id`, nullable, `ON DELETE SET NULL`.

**Nullable** because the Label Studio is also a standalone tool. A shelf tag for
a bottle nobody is running a campaign on is a real label, not an orphan.

**SET NULL** for the same reason as `creative_id` beside it, only stronger: a
label is a physical card clipped to a shelf. Deleting the strategy that inspired
it must not delete the design of something still hanging up in the aisle.

**Recorded at creation, never inferred.** The only moment we honestly know which
campaign a label was made for is the moment the owner made it from inside that
campaign. Existing rows are **not backfilled** — we have no record of what they
were for, and a guess stored in the same column as a fact can never be told
apart from one again.

The step now says *"2 labels for this campaign"*, or *"6 saved in Label Studio,
none for this campaign"*. Unlinked labels are counted and named, because silence
would read as "you have no labels", which is false.

---

## 3. The package — a second rendering, never a second opinion

`GET /workspace/{strategy_id}/package` → one ZIP:

```
labor-day-weekend-whiskey-push/
  README.txt                     what's here, and what isn't yet
  campaign-summary.pdf           the brief, printable
  ad/advertisement.png
  labels/01-buffalo-trace.png …  rendered at print resolution
  labels/print-sheet.pdf         print, then cut
  copy/social.txt · email.txt · sms.txt
  copy/platform/instagram.txt · facebook.txt · …
```

`build()` is handed **the exact dict `build_state()` put on the screen**. It
takes no strategy row and no session, so it *cannot* re-merge a copy override
differently from the page. Copy resolution moved into
`campaign_workspace.resolve_copy()`, used by both. An owner who found the AI's
original SMS in the ZIP after rewriting it on screen would discover the
difference at the printer, or through his customers.

**A missing piece is named, never fatal.** Half a campaign still packages; the
README says what is absent and where to make it. Every fetch is guarded
individually — one label that will not render, or an ad image lost to a
redeploy, must not deny the owner the rest of his own work.

The summary sheet is drawn with **Pillow**, like every label and print sheet in
this codebase. One imaging stack to keep working, no new dependency, and a PDF
that looks like the labels sitting beside it in the folder.

---

## 4. Embedding — how state is shared

The rule: **derived campaign data has one supply line, the server.** Nothing on
the client caches it and no component hands it to another.

```
GET /creative/campaign-context/:id ──prefill──▶ useAdCreator ──▶ form (both places)
GET /creative/:id ─────────────────latest ad──▶ useAdCreator
                                   generate ──▶ POST /creative/generate
                                                     │ onGenerated()
GET /workspace/:id ──state──▶ CampaignWorkspace ◀────┘  (re-fetch, recompute)
```

**One hook per tool, not one component per place.**
`hooks/useAdCreator.js` and `hooks/useLabelStudio.js` hold everything that used
to be page state. `Creative.jsx` and `CampaignAdSection` render the same
`AdCreatorForm`; `LabelStudio.jsx` and `CampaignLabelsSection` render the same
`LabelEditor` and `LabelLibrary`. The pages keep only what is genuinely a page —
the strategy picker, the handoff banner, the dashboard-action banner.

**The prefill is always fetched, never passed down.** `GET /workspace/{id}`
already carries a copy of the campaign context, so a prop would have saved a
request — and would have filled the ad form from a snapshot taken when the
workspace loaded, making the workspace a second, ageing source of prefills
beside the one `CampaignContext` was built to be. That endpoint is pure mapping,
no model call, so the second request costs almost nothing and buys a rule that
cannot rot.

**No React context provider.** A client-side cache of server-derived campaign
data is the same mistake wearing a hook.

**The sections report THAT something landed, never what.** `onGenerated` /
`onSaved` re-read `GET /workspace/{id}`; nothing on the client sets a done flag.
Progress stays computed server-side from the real assets — 23.7's rule, intact.

**The rail still comes from the server.** `EMBEDDED = { ad, labels }` says only
which of the server's routes this page now renders itself. Anything not listed
keeps linking out, so adding a step server-side can never leave a dead square.

---

## 5. Files

**New — backend**
| File | Purpose |
|---|---|
| `alembic/versions/e2b74c1a95d3_label_designs_strategy_id.py` | the migration |
| `services/campaign_package.py` | ZIP + summary PDF, pure `build()` + thin `collect_assets()` |
| `tests/test_campaign_package.py` | 22 tests |

**New — frontend**
| File | Purpose |
|---|---|
| `hooks/useAdCreator.js` · `hooks/useLabelStudio.js` | the state, owned once |
| `components/adcreator/AdCreatorForm.jsx` · `AdResult.jsx` | one ad form, one result |
| `components/labelstudio/LabelEditor.jsx` · `LabelLibrary.jsx` | one editor, one library |
| `pages/campaign/CampaignAdSection.jsx` · `CampaignLabelsSection.jsx` | the embeds |

**Modified:** `models/label_design.py` · `services/label_design_service.py` ·
`services/campaign_workspace.py` · `routes/label_studio.py` · `routes/workspace.py` ·
`schemas/label_studio.py` · `pages/Creative.jsx` · `pages/LabelStudio.jsx` ·
`pages/CampaignWorkspace.jsx` · `api/client.js`

---

## 6. API changes

| Method | Path | Change |
|---|---|---|
| GET | `/workspace/{strategy_id}/package` | **new** — ZIP download |
| GET | `/label-studio/labels?strategy_id=` | optional filter |
| POST | `/label-studio/labels` | body accepts `strategy_id` |
| — | `LabelOut` | now carries `strategy_id` |

---

## 7. Two bugs that fell out of the refactor

1. **The Ad Creator fetched the hero product's photo and facts twice** — once via
   the campaign context, once straight from the library — and the second write
   was **not** guarded by `touched`, so it could overwrite an owner's edit.
   One supply line, and the bug goes with the duplicate.
2. **Switching campaigns reset in an effect**, letting one frame paint the
   previous campaign's ad under this campaign's name. It now resets during
   render, so that state is never committed.

---

## 8. Commands

```bash
cd ~/Desktop/LiquorIQ/backend && source venv/bin/activate
alembic upgrade head              # → e2b74c1a95d3
pytest -q                         # 614 passed
uvicorn app.main:app --reload

cd ../frontend && npm run dev
```

---

## 9. Testing checklist

- [ ] `alembic upgrade head`, restart uvicorn
- [ ] Open `/campaign/<strategy_id>` → the Advertisement and Shelf labels sections render
- [ ] Generate an ad **in the workspace** → progress ticks Advertisement without a reload of the page
- [ ] Change the price, navigate away and back → your edit is still there, prefill has not overwritten it
- [ ] Save a label in the workspace → it appears under "Labels for this campaign" and the step ticks
- [ ] Open `/labels` directly → the full drawer is still listed, editor unchanged
- [ ] Open `/labels?strategy=<id>` → notice shown; a saved label counts towards that campaign
- [ ] **Download campaign** on a complete campaign → ZIP has ad, labels, sheet, copy, summary PDF
- [ ] **Download campaign** on an empty one → still downloads; README names what is missing
- [ ] Edit the SMS, save, download → the ZIP contains your edit, not the AI's original
- [ ] Click Advertisement / Shelf labels on the rail → scrolls; other steps still link out
- [ ] `pytest -q` → 614

---

## 10. What is still missing

1. **Nothing executes a schedule.** No worker reads `scheduled_for`. Unchanged
   from 23.7, and still the largest honesty gap in the workspace — the UI and
   the API both say so out loud, and the README in the ZIP repeats it.
2. **`alembic upgrade head` has not been run against a live database by me** —
   no Postgres in the environment I built this in. The migration was verified
   offline with `alembic upgrade --sql` (and its downgrade), so the DDL is
   correct, but run it on your machine before trusting it.
3. **No frontend tests.** The repo has none, and adding a test stack mid-phase
   would have been scope creep — but `useAdCreator` and `useLabelStudio` are now
   plain functions of props, which is the shape that makes testing them cheap.
   That is the next thing I would do.
4. **A label opened from the library and edited inside a campaign keeps its
   original campaign** (or none). Only creation stamps. Re-assigning is a
   product decision — "move this label to this campaign" — not a default.
5. **The package has no size ceiling.** Twenty labels at 300 DPI is a large ZIP
   built in memory. Fine at a shop's scale; it would need streaming before it
   was fine at a chain's.
6. **`labels/print-sheet.pdf` is always A4, 4-up.** The owner's chosen sheet
   settings live in the editor's state, not in anything the packager can read.

---

## 11. Interview notes

**"Why fetch the campaign context twice when the workspace already has it?"**
Because the workspace's copy is a snapshot from page load, and the moment it
becomes the ad form's prefill it is a second supply line for derived data — the
exact thing CampaignContext exists to prevent. The endpoint is pure mapping with
no model call, so the request is nearly free; the invariant is not. Cheap thing
bought, expensive thing avoided.

**"Why not a CampaignContext provider on the client?"**
That is a cache of server-derived data, and caches need invalidation rules the
derived model deliberately does not have. Prop drilling here is one level deep.
A provider would have bought tidiness and sold correctness.

**"Why does the package take a dict instead of the strategy?"**
So it *can't* disagree with the screen. `build()` has no session and no ORM row,
so there is no way for it to re-merge an override differently from the page.
That is enforced by construction rather than by remembering.

**"Why can a half-finished campaign be downloaded?"**
Because it is his work. A README naming the two things not made yet is more
useful than a button that refuses. Withholding output until a checklist is
complete is the product deciding it knows better than the man running the shop.

**"Why is `strategy_id` nullable when every label in the workspace has one?"**
Because not every label is made in the workspace, and never will be. A NOT NULL
column would force a standalone shelf tag to claim membership of a campaign that
does not exist — a false row is worse than a null one.
