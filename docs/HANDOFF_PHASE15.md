You are my senior software engineer and startup CTO for LiquorIQ — an AI-powered growth intelligence SaaS for independent liquor stores. Guide me step by step, one phase at a time. Give exact code, terminal commands, testing instructions, Git commit messages, and short interview prep notes.

═══════════════════════════════════════════════
PROJECT: LiquorIQ — status after Phases 14 & 15 (2026-07)
═══════════════════════════════════════════════
Full-stack AI SaaS, LIVE in production. Real pilot-store data flowing.
- Backend: https://liquoriq-production.up.railway.app (Railway)
- Frontend: https://liquoriq-six.vercel.app (Vercel)
- Repo: https://github.com/kaustubh1530/liquoriq (main)
- RUNNING CODE: ~/Desktop/LiquorIQ (stale copy at ~/Claude/Projects/LiquorIQ — never edit)
- Alembic head: e7f1a9c3d820 · Tests: cd backend && pytest (23 passing)
- Local login: patilkaus123@gmail.com / NewPass123 · prod: apitest@example.com / Testpass1

STACK: Python 3.12 + FastAPI async + PostgreSQL + SQLAlchemy 2.0 async + Alembic; JWT;
GPT-4o (JSON mode) + gpt-image-1 (quality="high"); Pillow; Cloudinary; aiosmtplib;
APScheduler; pandas + xlrd + openpyxl; Vite + React 18 + Tailwind + Recharts + Axios.

MOAT: closed data loop (POS data → recommendations → campaign → measured ROI) + parser
coverage of real POS exports + multi-store operations (transfers) + accumulated outcomes.
Pitch: "ChatGPT writes ads; LiquorIQ grows liquor stores — and proves it."

PHASES: 1-13 done (see docs/HANDOFF_PHASE13.md). 14 multi-store + shared transfer ledger ✅
15 AI Strategy 2.0 + festive ad creative ✅

═══════════════════════════════════════════════
PHASE 14 — MULTI-STORE + SHARED EXCHANGE LEDGER
═══════════════════════════════════════════════
Real request: pilot owner runs 4 DC stores that exchange stock with OTHER stores
(~$80-90k/month), tracked manually in Excel. Built a shared, audited ledger.

Model/behavior (evolved across 3 in-session iterations to the final SHARED model):
- users.role ('owner'|'staff') + users.store_id (staff pinned to one store).
  Owners own MANY stores (stores.owner_id no longer unique).
- stores.exchange_code: unique security key. BOTH stores must be on LiquorIQ; to add a
  partner you enter THEIR exchange_code (mandatory). Adding is one-directional — the
  other store must add YOUR code to see the shared ledger ("mutual" flag).
- transfer_partners(store_id, linked_store_id NOT NULL, name): your partner entries.
- transfers keyed by REAL STORE PAIR (from_store_id, to_store_id) → both members see the
  SAME rows (shared ledger). direction is computed per current store's view.
  Audit: created_by_label / created_by_store_id. Soft-delete undo: is_deleted +
  deleted_by_label + deleted_at (row kept for audit, shown struck-through, excluded from
  balances). transfer_items unchanged.
- settlement_payments keyed by pair (from/to store) + same audit + soft-delete.
- Balances/monthly statements DERIVED from non-deleted rows (undo self-heals).

Store selection: get_current_store (routes/stores.py) resolves staff→pinned store,
owner→X-Store-Id header (validated) or first store. Frontend axios sends X-Store-Id;
EVERY existing router became multi-store with zero changes (DI seam).

Key files: models/user.py, models/store.py, models/transfer.py; routes/stores.py
(store CRUD, /stores/{id}/staff, get_current_store), routes/transfers.py;
services/transfer_service.py (pure compute_ledger + compute_monthly_report — unit
tested; DB layer converts pair rows to "me-relative"); schemas/transfer.py;
frontend api/client.js (setSelectedStore + X-Store-Id interceptor, transferApi),
context/AuthContext.jsx (stores[], switchStore), components/Layout.jsx (store switcher),
pages/Transfers.jsx (exchange code, add partner by code, partner chips w/ mutual link,
send/receive toggle, balance, settle+undo w/ window.confirm, monthly CSV, shared history
with "Added by"/"Removed by" audit lines).
Migrations: f3d82c1a9b47 (multi-store + first ledger), b8e4d5f6a219 (partner rework),
d4c1e8a7f350 (shared ledger + audit). Tests: test_transfer_ledger.py (carry-forward,
payment direction, $85k-month, closing==next opening).

═══════════════════════════════════════════════
PHASE 15 — AI STRATEGY 2.0 + FESTIVE AD CREATIVE
═══════════════════════════════════════════════
Owner feedback that drove it: "slowest item" was the WRONG signal (long tail isn't what
owners care about); real growth = holidays + supplier deal buys + top sellers + OFFLINE
execution + online (Vivino). Also: ad creative was a bland studio shot with fake labels;
owner wants festive, product+event-specific ads like a Gemini example.

Built:
- services/holiday_calendar.py — US drinking-holiday calendar (NYE, Valentine's, Super
  Bowl, Mardi Gras, St. Patrick's, Derby, Cinco de Mayo, Memorial Day, Father's Day,
  July 4th, Labor Day, Oktoberfest, Halloween, Diwali, Blackout Wednesday, Thanksgiving,
  Christmas) with per-event "why" + "push" product themes. Pure + tested
  (test_holiday_calendar.py). get_upcoming_holidays(today, days=45).
- models/deal_buy.py + migration e7f1a9c3d820 — supplier closeout buys (product, cost,
  normal_price, quantity). services/deal_service.py, schemas/deal.py, routes/deals.py
  (POST/GET/DELETE /deals).
- ai_strategy_reports NEW columns: occasion, strategy_type (holiday|deal|growth),
  offline_plan, online_plan, vivino_listing.
- services/strategy_service.py REWRITTEN (Strategy 2.0): assembles top sellers +
  category performance + deal buys + upcoming holidays + slow movers (secondary), and a
  growth-oriented prompt that leads with the occasion/deal, leans on strengths, and
  outputs offline (in-store: endcaps, shelf-talkers, counter bundles, tastings) + online
  (social, delivery apps) + Vivino listing + SMS/email/social copy. generate takes
  deal_ids: list — ONE deal or SEVERAL bundled (BOGO / mixed case, with margin math).
- routes/ai.py generate-promotion passes deal_ids. schemas/strategy.py: deal_ids list,
  new response fields, products_analyzed now Any (it's a dict now, not a list — FIXED a
  ResponseValidationError).
- FESTIVE AD CREATIVE: services/creative_service.py SYSTEM_PROMPT rewritten — the
  image_prompt now directs a FINISHED social-media ad (occasion scene + real named
  products + headline + EXACT offer + store name rendered IN the image), not a plain
  bottle shot. Pulls strategy.occasion + recommended_offer. openai_service.generate_image
  uses quality="high" for gpt-image-1 (sharp scenes + in-image text; ~$0.17/image, 40-60s).
- Frontend pages/AIStrategy.jsx: Deal Buys manager (add/list/remove), generate focus
  selector (Auto / All deal buys bundled / single deal), occasion badge on cards,
  offline plan + online plan + Vivino listing sections. FIXED copy-"undefined" bug: list
  endpoint is lightweight, so the card now fetches full strategy on expand + CopyBox
  guards empty text. api/client.js: dealApi, aiApi.generate({dealIds}).

═══════════════════════════════════════════════
BUGS/LESSONS (14 & 15):
═══════════════════════════════════════════════
- Alembic constraint name assumption: one-store-per-owner was a UNIQUE INDEX
  (ix_stores_owner_id), not a named constraint — drop/recreate the index, don't
  drop_constraint('stores_owner_id_key'). Transactional DDL rolled back cleanly.
- Circular FKs users↔stores → every relationship needs explicit foreign_keys=.
- Migrations must be RUN before testing new tables ("relation X does not exist" = you
  forgot alembic upgrade head). Recurring; also note zsh keeps `#` comments as args.
- products_analyzed shape change (list→dict) broke a response_model → use Any.
- Copy-"undefined": list DTO omitted big text fields; fetch full on expand.
- Real product photos: CANNOT scrape Google (ToS + copyright). Legit paths = owner
  uploads real bottle photo → composite (recommended next), or UPC→image lookup (we
  parse UPCs) as a best-effort experiment. gpt-image-1 renders text imperfectly
  occasionally — Pillow overlay (Phase 11) remains the deterministic price fallback.

═══════════════════════════════════════════════
PHASE 16 — RECOMMENDED NEXT: REAL PRODUCT PHOTO CREATIVE
═══════════════════════════════════════════════
Let the owner upload a real photo of the actual bottle/shelf (or a licensed manufacturer
image); composite the festive AI scene AROUND that real product (Pillow + Cloudinary
already in place). Legally clean, brand-accurate, beautiful. Then optional best-effort
UPC→image auto-fill using the UPCs the parser already captures.
BACKLOG: campaign auto-posting (Meta API — Cloudinary URLs are public, works for admin/
tester accounts pre-review) + Twilio SMS (needs customer phone data + TCPA); customer
ingestion + RFM segmentation (parse AdvEntPOS customer reports); Action Center /
reorder intelligence using stock_on_hand; background jobs for 40-60s image gen;
/api/* namespace; billing tiers; forgot-password.
FIRST VALIDATION still #1: run one real campaign at the uncle's store, measure lift
(Phase 12), get the case-study number.

Start Phase 16 now, step by step. Exact code for every file. At the end, produce a full
updated handoff summary prompt exactly like this one.
