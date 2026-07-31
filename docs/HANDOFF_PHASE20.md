You are my senior software engineer and startup CTO for LiquorIQ — an AI-powered growth intelligence SaaS for independent liquor stores. Guide me step by step, one phase at a time. Give exact code, terminal commands, testing instructions, Git commit messages, and short interview prep notes.

═══════════════════════════════════════════════
PROJECT: LiquorIQ — status after Phase 20 (2026-07-25)
═══════════════════════════════════════════════
Full-stack AI SaaS, LIVE in production, real pilot-store data.
- Backend: https://liquoriq-production.up.railway.app (Railway)
- Frontend: https://liquoriq-six.vercel.app (Vercel)
- Repo: https://github.com/kaustubh1530/liquoriq (main)
- RUNNING CODE: ~/Desktop/LiquorIQ (stale copy at ~/Claude/Projects/LiquorIQ — never edit)
- Alembic head: f1a3c8e290d4 · Tests: cd backend && pytest (50 passing)
- Local login: patilkaus123@gmail.com / NewPass123 · prod: apitest@example.com / Testpass1

STACK: Python 3.12 + FastAPI async + PostgreSQL + SQLAlchemy 2.0 async + Alembic; JWT;
GPT-4o (JSON) + gpt-image-1 (quality=high, images.edit real-photo compositing); Pillow;
Cloudinary; aiosmtplib; APScheduler; pandas+xlrd+openpyxl; Vite + React 18 + Tailwind +
Recharts + Axios.

PHASES 1-19 done (docs/HANDOFF_PHASE19.md + earlier). Phase 19 = customer ingestion + RFM
segmentation (Customer/CustomerPurchase, services/rfm.py, customer_parser, Customers page).

═══════════════════════════════════════════════
PHASE 20 — CUSTOMER-SEGMENT TARGETED AI STRATEGIES
═══════════════════════════════════════════════
Connect Phase 19 RFM segments to the Phase 7/15 strategy flow: owner picks product +
occasion + a customer SEGMENT (VIP/Loyal/New/At Risk/Inactive/High Value/Regular) → the AI
writes a campaign tuned to that audience. Reuses strategy generation, ROI tracking, RFM.
NO PII to GPT. NO messages sent.

MODEL (models/ai_strategy_report.py) + migration f1a3c8e290d4 (both NULLABLE → backward
compatible; existing strategies unaffected):
- target_segment (String) — which RFM segment the campaign targets (null = all customers).
- audience_snapshot (JSON) — AGGREGATED segment stats frozen AT GENERATION TIME so ROI stays
  stable when customers later move between RFM segments (req #9).

RFM ADDITIONS (services/rfm.py — PURE, tested):
- SEGMENT_PLAYBOOK[seg] = {behavior, objective, tone} — drives the GPT prompt (req #4).
- segment_stats(customers) → {size, total_spent, avg_spend, avg_visits, sms_opted_in,
  email_opted_in} — AGGREGATES ONLY (no name/email/phone → privacy, req #6).
- audience_warnings(stats) → deterministic warnings: empty segment / no channel consent /
  small audience (<SMALL_AUDIENCE=10) (req #10).

SERVICE (services/customer_service.get_segment_audience — store-scoped, req #2/#3/#6):
- Loads THIS store's customers, computes each one's RFM segment, filters to the target,
  returns segment_stats + warnings + SEGMENT_RECOMMENDATIONS + SEGMENT_PLAYBOOK. Raises on
  unknown segment. Only aggregates leave this function.

STRATEGY GENERATION (services/strategy_service.py):
- generate_promotion_strategy(..., target_segment) → validates the segment, fetches the
  store-scoped audience, raises if size 0, adds a TARGET AUDIENCE block (behavior + objective
  + tone + AGGREGATE stats only) to the prompt, and saves target_segment + audience_snapshot
  (playbook stripped) on the report. _build_user_prompt gained an `audience` arg; with no
  audience the prompt is byte-identical to before (backward compatible, tested).

ENDPOINTS:
- GET /customers/audience/{segment} → aggregate audience stats + warnings (routes/customers.py).
- POST /ai/generate-promotion now accepts target_segment (schemas/strategy.py:
  GeneratePromotionRequest.target_segment; StrategyResponse + StrategyListItem expose
  target_segment; StrategyResponse also returns audience_snapshot).

FRONTEND (pages/AIStrategy.jsx + client.js):
- customerApi.audience(segment); aiApi.generate now sends target_segment.
- "Target audience (optional)" dropdown populated from /customers/segments (segment · count),
  shown only when the store has customers. Selecting one shows an AUDIENCE PREVIEW card:
  size, avg spend, avg visits, SMS-opted-in, email-opted-in, deterministic warnings, and a
  note that only aggregates go to the AI. Strategy cards show a 🎯 target-segment badge.
- Empty/loading states handled (no segments → selector hidden; audienceLoading spinner).

RESPONSIBLE MARKETING (req #11): the strategy SYSTEM_PROMPT already enforces responsible
alcohol language; the audience block reinforces consent-aware, age-appropriate targeting.
Distribution (SMS/Meta) intentionally NOT built here.

TESTS (50 total; tests/test_segment_targeting.py adds 9): aggregate calculations, empty
segment, all three warnings + healthy (no warnings), playbook completeness, PROMPT PRIVACY
(no PII, aggregates present), backward-compat (no "TARGET AUDIENCE" without a segment).
Store isolation is enforced by store_id scoping in get_segment_audience (query layer).

═══════════════════════════════════════════════
RUN / TEST / SHIP:
═══════════════════════════════════════════════
  cd ~/Desktop/LiquorIQ/backend && source venv/bin/activate
  alembic upgrade head          # → f1a3c8e290d4 (target_segment + audience_snapshot)
  pytest -q                     # → 50 passed
  uvicorn app.main:app --reload
  # frontend: cd ~/Desktop/LiquorIQ/frontend && npm run dev
  # Customers → import outputs/sample_customers.csv (if not already) → AI Strategy →
  #   pick "Target audience" (e.g. At Risk) → preview shows size/spend/visits/consent + warnings →
  #   Generate → strategy card shows 🎯 badge; copy is tuned to that segment.
  git add -A && git commit -m "feat(phase-20): customer-segment targeted AI strategies (aggregates-only prompt, frozen audience snapshot, warnings, tests)"
  git push origin main

INTERVIEW NOTES:
- Privacy-by-design: only aggregate segment stats reach the LLM — never customer records.
  The aggregation function is the trust boundary, and a test asserts no PII in the prompt.
- Snapshotting the audience at generation time makes ROI reproducible even though RFM segments
  are derived and drift as customers behave — freeze the denominator you measured against.
- Backward compatibility: nullable columns + an optional prompt arg → old strategies and the
  no-segment path are unchanged; a test pins the prompt shape.
- Segment playbook (behavior/objective/tone) turns a taxonomy into actionable prompt context —
  the AI writes a win-back for "At Risk" vs a reward for "VIP".

═══════════════════════════════════════════════
PHASE 21 CANDIDATES:
═══════════════════════════════════════════════
A. DISTRIBUTION: Twilio SMS + email to opted-in customers of a targeted segment (TCPA opt-out,
   consent model + segments + audience snapshot already in place) and/or Meta auto-post
   (Cloudinary URLs public → tester accounts pre-review).
B. Segment-aware ROI: compare the targeted segment's spend before/after the campaign using the
   frozen audience_snapshot (extends Phase 12).
C. Background jobs for 40-60s image gen; billing tiers; forgot-password; /api/* namespace;
   fee-line filter in the sales parser.
FIRST VALIDATION still #1: run one REAL campaign at the uncle's store, measure lift (Phase 12).

Start the chosen phase now, step by step, exact code for every file. At the end, produce a full
updated handoff summary prompt exactly like this one.
