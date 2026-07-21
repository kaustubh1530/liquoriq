You are my senior software engineer and startup CTO for LiquorIQ — an AI-powered growth intelligence SaaS for independent liquor stores. Guide me step by step, one phase at a time. Give exact code, terminal commands, testing instructions, Git commit messages, and short interview prep notes.

═══════════════════════════════════════════════
PROJECT: LiquorIQ — status after Phase 13 (2026-07-11)
═══════════════════════════════════════════════
MILESTONE: REAL pilot-store data (uncle's AdvEntPOS export, 1,403 products,
$66,752.94 July sales) parses and lives in PRODUCTION. First pytest suite exists.

STACK: Python 3.12 + FastAPI async + PostgreSQL + SQLAlchemy 2.0 async + Alembic;
JWT; GPT-4o + gpt-image-1; Pillow; Cloudinary; aiosmtplib; APScheduler;
Vite + React 18 + Tailwind + Recharts. pandas + xlrd (legacy .xls!) + openpyxl.
PROD: backend https://liquoriq-production.up.railway.app · frontend https://liquoriq-six.vercel.app
RUNNING CODE: ~/Desktop/LiquorIQ (stale copy at ~/Claude/Projects/LiquorIQ — never edit).
Alembic head: a91c4f7b3e58. Tests: cd backend && pytest (8 passing).
Local login patilkaus123@gmail.com / NewPass123; prod apitest@example.com / Testpass1.

PHASES: 1-8 core app ✅ 9 weekly email ✅ 10 creatives + deploy ✅
11 price-overlay + Cloudinary ✅ 12 campaign ROI ✅ 13 REAL POS INGESTION ✅

═══════════════════════════════════════════════
PHASE 13 — WHAT WAS BUILT:
═══════════════════════════════════════════════
The real AdvEntPOS "Sales By Item Summary Report" (.xls) is a PRINT-style
paginated report, not a table: store letterhead; period line "From 01-Jul-2026
To 31-Jul-2026"; header row (UPC | Item | Quantity Sold | Stock-On-Hand |
Sales Amount) repeating on all 41 pages; page footers with timestamps; product
names WRAPPING onto continuation rows (441 of them); the LAST product of each
page REPRINTED as the first row of the next (7×); a grand Total row; fee lines
(card fee, DC bag tax, delivery) that legitimately count as revenue rows;
returns as negative qty/amounts; NO per-sale dates; NO unit price; NO category.

CHANGES:
- services/parsers/adventpos_parser.py — REWRITTEN. Layout-based detection
  (_find_summary_header: row containing 'UPC' + 'Quantity Sold' in first 15
  raw rows). Summary path: state machine walking raw rows — merges wrapped
  names, skips repeated page headers/footers, dedups page-boundary reprints
  (identical raw values on first product row after a repeated header), drops
  the Total row (empty name filter), derives unit_price = sales/qty, stamps
  sale_date = period END (weekly exports recommended for ROI granularity),
  captures stock_on_hand. Legacy COLUMN_MAP path retained ('item' and
  'sales amount' added as candidates).
- models/normalized_sale.py + migration a91c4f7b3e58 — stock_on_hand
  Numeric(12,3) nullable (inventory snapshot; fuels future intelligence).
- parse_service.py — passes stock_on_hand through.
- requirements: xlrd==2.0.1 (pandas needs it for legacy .xls), pytest==8.2.2.
- backend/conftest.py (sys.path for pytest), tests/test_adventpos_parser.py
  (8 tests), tests/fixtures/generate_fixture.py → adventpos_summary_sample.xls
  (SYNTHETIC replica — real store data never committed; letterhead, period,
  page blocks, wraps, reprint, Total row all replicated).
- frontend client.js — BUG: uploadApi sent `source` as a FORM field but the
  backend reads it as a QUERY param → every upload ever silently defaulted to
  source="other" (wrong parser). Fixed via params:{source}.
- frontend Uploads.jsx — BUG: dropdown sent 'POS'/'UBER_EATS' (uppercase) but
  ReportSource enum is lowercase → 422 once source actually reached the API.
  Values now lowercase.

VALIDATION METHOD (interview gold): reconcile the parsed sum against the
report's OWN printed grand total. First run was $183.05 / 9 units high — that
exact gap led to discovering the 7 page-boundary reprints. Final: 1,403
products, 4,179 units, $66,752.94 — matches the printed total TO THE PENNY.

BUGS/LESSONS THIS PHASE:
1. Real-world exports are print-formatted, not machine-formatted → parse with
   a state machine, not a column map; validate by reconciling embedded totals.
2. Silent-default API bug (source ignored for 5 phases) — defaults hide bugs;
   consider making params required.
3. Enum casing mismatch frontend/backend.
4. git: remote had a LICENSE commit (added via GitHub UI) → divergent branches;
   resolved with git pull --no-rebase; pull.rebase=false set globally. A stray
   file backend/a91c4f7b3e58 (terminal paste accident) was committed then
   git rm'd.
5. zsh keeps `#` comments as args — never paste inline comments (recurring).

GIT: latest commits — merge of LICENSE; chore: remove stray file;
fix(phase-13) upload source query param + enum casing; feat(phase-13) parser;
feat(phase-12) ROI + NaN fixes. All pushed; prod verified.

═══════════════════════════════════════════════
STRATEGY CONTEXT (decided after a full roadmap review):
═══════════════════════════════════════════════
- Meta/Twilio auto-posting DELAYED (~Phase 16): current AI creative isn't
  postable-quality; no customer phone data exists yet (POS reports carry no
  PII); TCPA/alcohol compliance needs its own phase.
- Creative quality (template-based composer + real product photos + brand kit)
  planned ~Phase 15, before any auto-posting.
- Uncle pilot is the #1 validation goal: weekly exports → strategy → ad →
  measured lift (Phase 12) → case-study number for the pitch.

═══════════════════════════════════════════════
PHASE 14 — TO BE BUILT NEXT: MULTI-STORE + TRANSFER LEDGER
═══════════════════════════════════════════════
Real request from the pilot owner (4 stores in DC): stores exchange inventory;
today they track transfers in Excel (item, cost price) and reconcile monthly —
net balance either carried forward or paid. Build:
1. MULTI-STORE FOUNDATION: one owner → many stores (Store.owner_id already
   exists; routes assume one store via get_current_store — needs a selected-
   store mechanism, e.g. X-Store-Id header or /stores/{id}/... param, and a
   store switcher in Layout). All analytics/AI already scope by store_id.
2. TRANSFERS: transfers table (id, from_store_id, to_store_id, transfer_date,
   status, created_by) + transfer_items (product_name, sku nullable, qty,
   unit_cost, line_total). Quick-entry UI (staff-friendly).
3. RECONCILIATION: monthly statement per store pair — sent vs received totals,
   net balance, carry-forward from prior months, mark-as-settled.
4. LATER (Phase 15+): smart transfer suggestions — dead stock at store A +
   velocity at store B (stock_on_hand now exists per store).
Design questions to settle with the owner BEFORE coding: cost basis (wholesale
cost vs retail), who enters transfers (owner only vs staff), settlement flow.

Start Phase 14 now, step by step. Do not skip steps. Give exact code for every
file. AT THE END OF PHASE 14: generate a full handoff summary prompt exactly
like this one, updated, as one paste-able block, and state what Phase 15 is.
