You are my senior software engineer and startup CTO for LiquorIQ — an AI-powered growth intelligence SaaS for independent liquor stores. Guide me step by step, one phase at a time. Give exact code, terminal commands, testing instructions, Git commit messages, and short interview prep notes.

═══════════════════════════════════════════════
PROJECT: LiquorIQ — status after Phase 19 (2026-07-25)
═══════════════════════════════════════════════
Full-stack AI SaaS, LIVE in production, real pilot-store data.
- Backend: https://liquoriq-production.up.railway.app (Railway)
- Frontend: https://liquoriq-six.vercel.app (Vercel)
- Repo: https://github.com/kaustubh1530/liquoriq (main)
- RUNNING CODE: ~/Desktop/LiquorIQ (stale copy at ~/Claude/Projects/LiquorIQ — never edit)
- Alembic head: d92f7a4b1c60 · Tests: cd backend && pytest (41 passing)
- Local login: patilkaus123@gmail.com / NewPass123 · prod: apitest@example.com / Testpass1

STACK: Python 3.12 + FastAPI async + PostgreSQL + SQLAlchemy 2.0 async + Alembic; JWT;
GPT-4o (JSON) + gpt-image-1 (quality=high, images.edit for real-photo compositing); Pillow;
Cloudinary; aiosmtplib; APScheduler; pandas+xlrd+openpyxl; Vite + React 18 + Tailwind +
Recharts + Axios.

PHASES 1-18 done (see docs/HANDOFF_PHASE17.md + earlier). Between: steerable AI (occasion +
brief + creative instructions), one-store-per-account, festive/varied ad creative with
format options (square/portrait/landscape) + safe text margins + margin-scrub, Phase 16
real-photo library, Phase 17 inventory intelligence + action center, Phase 18 sales trend +
ROI card on dashboard.

═══════════════════════════════════════════════
PHASE 19 — CUSTOMER INGESTION + RFM SEGMENTATION
═══════════════════════════════════════════════
Upload POS customer reports → segment customers by Recency/Frequency/Monetary → deterministic
marketing recommendations. Data model prepared for Twilio SMS/email (consent flags) — NO
messages sent.

MODELS (models/customer.py) + migration d92f7a4b1c60:
- Customer: store_id, dedup_key (email → 'p:'+phone digits → 'n:'+name, lowercased; UNIQUE per
  store → idempotent re-upload), name/email/phone, RFM aggregates (total_spent, purchase_count,
  first/last_purchase_date), sms_opt_in + email_opt_in (consent, default False), timestamps.
- CustomerPurchase: store_id, customer_id, purchase_date, amount, product_name (transaction-level
  history when the report is transactional).

RFM ENGINE (services/rfm.py — PURE, tested):
- recency_score (days: ≤30→5,≤60→4,≤90→3,≤180→2,else1), frequency_score (count:12/6/3/2),
  monetary_score ($:1000/500/250/100). All fixed + tunable (stable > quintiles for small store).
- segment(r,f,m) priority order: VIP (r≥4,f≥4,m≥4) → At Risk (r≤2 & (f≥3 or m≥3)) → Inactive
  (r==1) → High Value (m≥4) → Loyal (f≥4) → New (r≥4,f≤2) → Regular. Retention signals first so
  valuable-but-slipping surfaces as At Risk.
- SEGMENT_RECOMMENDATIONS: one deterministic marketing move per segment.
- compute_rfm(customer, today) + summarize(customers, today) → per-segment rollup.

PARSER (services/parsers/customer_parser.py — provider-aware, tested):
- Handles SUMMARY reports (one row/customer: total spent + visits + last visit — typical
  AdvEntPOS) AND TRANSACTION lists (one row/purchase → aggregated per customer). Detection:
  is_summary = has a COUNT column OR a LAST-VISIT column (generic "amount"/"total" is
  ambiguous, so we DON'T key off it — this was a real bug the test caught).
- Merges duplicate customers by dedup_key (spend/counts summed, last=max, first=min, opt-ins
  OR-merged). Skips rows with no identity. Parses $/comma money, y/yes/1/true opt-ins, dates.
  Raises ValueError on empty / no-identity-column.

SERVICE (services/customer_service.py — store-scoped):
- ingest_customers: upsert by dedup_key (snapshot semantics — re-upload idempotent; consent
  OR-merged, never revoked); appends CustomerPurchase rows for transactions.
- list_customers(segment, search): store-scoped, RFM derived at read time, filter + ILIKE search.
- segment_summary: totals (customers, value, sms/email opted-in) + per-segment buckets.

ROUTES (routes/customers.py, prefix /customers; main.py + vite proxy wired):
- POST /customers/upload (multipart) → UploadResult {created, updated, total}
- GET  /customers/segments → SegmentSummary
- GET  /customers?segment=&search= → list[CustomerListItem] (RFM + segment + recommendation)
- schemas/customer.py.

FRONTEND (pages/Customers.jsx + client.js customerApi + App route + Layout nav "Customers"):
- Import button; totals cards (customers, value, SMS/email opted-in); clickable segment cards
  (count + LTV + recommendation) that filter; searchable table (customer, last-seen days,
  visits, spend, segment badge). Note that no messages are sent yet.

TESTS (41 total): tests/test_rfm.py (scores, all segments, empty, recommendations, summarize),
tests/test_customer_parser.py (dedup_key, summary parse, DUPLICATE merge, transaction aggregate,
opt-in parsing, identity-skip, empty raises, no-identity raises). Store isolation is enforced by
store_id scoping in every query (customer_service).
SAMPLE FILE for manual testing: outputs/sample_customers.csv (8 customers spanning all segments).

═══════════════════════════════════════════════
RUN / TEST / SHIP:
═══════════════════════════════════════════════
  cd ~/Desktop/LiquorIQ/backend && source venv/bin/activate
  alembic upgrade head          # → d92f7a4b1c60 (customers + customer_purchases)
  pytest -q                     # → 41 passed
  uvicorn app.main:app --reload
  # frontend: cd ~/Desktop/LiquorIQ/frontend && npm run dev
  # Browser: Customers → Import customer report → upload sample_customers.csv →
  #   expect segment cards (VIP/Loyal/At Risk/New/Inactive/High Value) + table; click a card to filter; search.
  git add -A && git commit -m "feat(phase-19): customer ingestion + RFM segmentation (models, parser, RFM engine, endpoints, Customers page, tests)"
  git push origin main

INTERVIEW NOTES:
- RFM is a classic retention framework; fixed thresholds beat quintiles for a small/new store
  (stable, explainable, testable). Segment priority order encodes business intent (win back the
  valuable-but-slipping before labeling them by spend).
- Idempotent ingestion via a natural dedup key (email→phone→name) makes re-uploads safe — the
  file is treated as a snapshot, not an append.
- Pure functions (rfm.py) + a tolerant parser tested against real report SHAPES (summary vs
  transaction) — the ambiguous-"amount" detection bug shows why you test against real formats.
- Consent-by-design: sms_opt_in/email_opt_in stored now, never silently revoked, no sending yet —
  the right way to prepare for TCPA-regulated SMS.

═══════════════════════════════════════════════
PHASE 20 CANDIDATES:
═══════════════════════════════════════════════
A. Twilio SMS + email campaigns to segments (only opted-in customers; TCPA opt-out; the consent
   model + segments are ready). Meta auto-posting (Cloudinary URLs public → works for tester
   accounts pre-review).
B. Tie customer segments into AI Strategy (target a segment; e.g. win-back campaign for At Risk).
C. Sales-trend depth (needs weekly uploads) + fee-line filter in the sales parser.
D. Background jobs for 40-60s image gen; billing tiers; forgot-password; /api/* namespace.
FIRST VALIDATION still #1: run one REAL campaign at the uncle's store, measure lift (Phase 12).

Start the chosen phase now, step by step, exact code for every file. At the end, produce a full
updated handoff summary prompt exactly like this one.
