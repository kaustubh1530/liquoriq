You are my senior software engineer and startup CTO for LiquorIQ — an AI-powered growth intelligence SaaS for independent liquor stores. Guide me step by step, one phase at a time. Give exact code, terminal commands, testing instructions, Git commit messages, and short interview prep notes.

═══════════════════════════════════════════════
PROJECT: LiquorIQ — status after Phase 21 (2026-07-25)
═══════════════════════════════════════════════
Full-stack AI SaaS, LIVE in production, real pilot-store data.
- Backend: https://liquoriq-production.up.railway.app (Railway)
- Frontend: https://liquoriq-six.vercel.app (Vercel)
- Repo: https://github.com/kaustubh1530/liquoriq (main)
- RUNNING CODE: ~/Desktop/LiquorIQ (stale copy at ~/Claude/Projects/LiquorIQ — never edit)
- Alembic head: a5d9c2e714b8 · Tests: cd backend && pytest (53 passing)
- Local login: patilkaus123@gmail.com / NewPass123 · prod: apitest@example.com / Testpass1

STACK: Python 3.12 + FastAPI async + PostgreSQL + SQLAlchemy 2.0 async + Alembic; JWT;
GPT-4o + gpt-image-1; Pillow; Cloudinary; aiosmtplib (email); Twilio (SMS); APScheduler;
pandas+xlrd+openpyxl; Vite + React 18 + Tailwind + Recharts + Axios.

PHASES 1-20 done (docs/HANDOFF_PHASE20.md + earlier). Phase 19 = customers + RFM; Phase 20 =
segment-targeted AI strategies (target_segment + audience_snapshot, aggregates-only prompt).
Also earlier this session: manual "Add customer" (POST /customers, idempotent upsert).

═══════════════════════════════════════════════
PHASE 21 — DISTRIBUTION (SMS + EMAIL to opted-in customers)
═══════════════════════════════════════════════
Actually SEND a strategy's copy to the opted-in customers of its target segment. Compliance-
FIRST; nothing is sent by accident.

SAFETY / COMPLIANCE DESIGN:
- Recipients = ONLY customers with channel opt-in True AND NOT opted-out AND a usable address,
  filtered to the strategy's target_segment (customer_service.get_recipients, store-isolated).
- Suppression list: customers.sms_opted_out / email_opted_out (added this phase) — once opted
  out, never contacted again, and re-uploads NEVER clear it (ingestion only sets opt_in).
- SMS auto-appends "Reply STOP to unsubscribe." (TCPA) and truncates to ≤320 chars.
- SMS is a DRY RUN unless Twilio is configured (config empty → messages logged, not sent).
  Email uses the existing Gmail SMTP (already live) so email actually sends in prod.
- Every send requires an explicit POST + a frontend window.confirm; owner-only.
- Every recipient logged (MessageLog: sent/failed/dry_run) for an audit trail.

MODELS (models/campaign.py) + migration a5d9c2e714b8:
- Campaign: store_id, strategy_id, channel (sms|email), target_segment, status
  (sent|partial|failed|dry_run), recipients_total/sent/failed/skipped counts, created_by.
- MessageLog: per-recipient (customer_id, to_address, status, error).
- customers.sms_opted_out + email_opted_out (suppression).

SERVICES:
- services/sms_service.py — Twilio via asyncio.to_thread; is_configured(); build_sms_body()
  (append STOP + truncate); send_sms() returns {status, error}, never raises; DRY-RUN when
  unconfigured. Config: TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_FROM_NUMBER (empty=dry).
- services/campaign_delivery_service.py — preview_campaign (recipient count + sample + warnings,
  no send), send_campaign (loop recipients, SMS via twilio / email via send_html_email, log each,
  set Campaign counts+status), list_campaigns. Email HTML includes an unsubscribe line.
- customer_service.get_recipients + opt_out (suppress; sets opt_in False + opted_out True).
- requirements: twilio==9.2.3.

ROUTES (routes/campaigns.py, prefix /campaigns; main + vite wired):
- GET  /campaigns/preview?strategy_id&channel — no send
- POST /campaigns/send {strategy_id, channel} — owner only
- GET  /campaigns — history
- POST /campaigns/opt-out/{customer_id}?channel= — suppress

FRONTEND (pages/AIStrategy.jsx SendCampaign component + client.js campaignApi):
- On each expanded strategy card: "Send to customers" → SMS / Email → PREVIEW (opted-in
  recipient count in the target segment + sample message + warnings, e.g. "Twilio not
  configured — DRY RUN") → window.confirm (real vs dry run) → send → result (sent/failed).

TESTS (53 total; tests/test_sms_service.py adds 3): opt-out line always appended, long-copy
truncation keeps opt-out, dry-run never raises. Recipient consent filtering + opt-out
suppression are enforced at the query layer (get_recipients) — store-isolated; verified via
manual test (import sample_customers.csv → preview shows only opted-in in the segment).

RESPONSIBLE MARKETING (req): only consented, age-appropriate audiences; opt-out on every SMS;
suppression permanent; owner-gated; nothing auto-sends.

═══════════════════════════════════════════════
RUN / TEST / SHIP:
═══════════════════════════════════════════════
  cd ~/Desktop/LiquorIQ/backend && source venv/bin/activate
  pip install twilio==9.2.3
  alembic upgrade head          # → a5d9c2e714b8 (campaigns, message_logs, opt-out cols)
  pytest -q                     # → 53 passed
  uvicorn app.main:app --reload
  # frontend: cd ~/Desktop/LiquorIQ/frontend && npm run dev
  # Customers → import outputs/sample_customers.csv (has SMS/email opt-ins) →
  # AI Strategy → expand a strategy → Send to customers → Email → preview shows opted-in count →
  #   confirm → real email sends (SMTP live); SMS shows DRY RUN unless Twilio configured.
  # To enable real SMS: set TWILIO_ACCOUNT_SID/AUTH_TOKEN/FROM_NUMBER in .env (Railway vars in prod).
  git add -A && git commit -m "feat(phase-21): SMS+email distribution to opted-in segments (Twilio dry-run-safe, opt-out suppression, preview+confirm, audit log)"
  git push origin main

INTERVIEW NOTES:
- Compliance-by-construction: consent + suppression enforced in the recipient query (the single
  trust boundary); opt-out survives re-uploads; STOP auto-appended; dry-run default. You design
  regulated features so the safe path is the default and unsafe requires explicit action.
- Provider abstraction mirrors Cloudinary: unconfigured Twilio → dry-run, so dev/demo never
  sends real texts; same code sends for real once creds exist.
- Per-recipient MessageLog = auditability (who was contacted, status) — essential for TCPA.

═══════════════════════════════════════════════
PHASE 22 CANDIDATES:
═══════════════════════════════════════════════
A. Meta (Instagram/Facebook) auto-posting of the ad creative (Cloudinary URLs are public → works
   for admin/tester accounts pre app-review).
B. Segment-aware ROI: measure the targeted segment's spend before/after using audience_snapshot.
C. Public unsubscribe link (tokenized) in emails/SMS → self-serve opt-out endpoint.
D. Cleanup: fee-line filter in the sales parser (bag tax/delivery showing as inventory); weekly
   export habit for sharper velocity/ROI; background jobs; billing tiers; forgot-password.
FIRST VALIDATION still #1: run one REAL campaign at the uncle's store, measure lift (Phase 12).

Start the chosen phase now, step by step, exact code for every file. At the end, produce a full
updated handoff summary prompt exactly like this one.
