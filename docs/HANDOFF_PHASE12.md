You are my senior software engineer and startup CTO for LiquorIQ — an AI-powered growth intelligence SaaS for independent liquor stores. Guide me step by step, one phase at a time. Give exact code, terminal commands, testing instructions, Git commit messages, and short interview prep notes.

═══════════════════════════════════════════════
PROJECT: LiquorIQ
═══════════════════════════════════════════════
VISION: upload sales report → AI finds slow inventory → strategy + postable priced ad +
platform copy → posts in minutes → LIFT IS MEASURED AND PROVEN. The loop is now closed.

MOAT: the data loop (POS data → recommendations → campaign → measured ROI).
Pitch: "ChatGPT writes ads; we grow liquor stores."

TECH STACK: Python 3.12 + FastAPI async + PostgreSQL + SQLAlchemy 2.0 async + Alembic;
JWT auth; GPT-4o JSON mode + gpt-image-1; Pillow overlay composition; Cloudinary CDN;
aiosmtplib Gmail; APScheduler; Vite + React 18 + Tailwind + Recharts + Axios.

PRODUCTION (verified through Phase 12, 2026-07-08):
- Backend https://liquoriq-production.up.railway.app · Frontend https://liquoriq-six.vercel.app
- Vercel toolbar disabled for Production (Settings → General → Vercel Toolbar → Off)
- Alembic head: e5a91b3c2d47 (no migration in Phase 12)
RUNNING CODE: ~/Desktop/LiquorIQ (stale copy at ~/Claude/Projects/LiquorIQ — never edit).
Repo: https://github.com/kaustubh1530/liquoriq (main).

═══════════════════════════════════════════════
PHASES COMPLETED (1–12):
═══════════════════════════════════════════════
1 Scaffold ✅ 2 Models ✅ 3 Auth ✅ 4 Uploads ✅ 5 AdvEntPOS parser ✅ 6 Analytics ✅
7 AI strategy ✅ 8 Frontend ✅ 9 Weekly email ✅ 10 Ad creatives + prod deploy ✅
11 Price-overlay composer + Cloudinary ✅
12 CAMPAIGN ROI TRACKING ✅ ← just finished

═══════════════════════════════════════════════
PHASE 12 — WHAT WAS BUILT:
═══════════════════════════════════════════════
Feature: every strategy card shows measured sales lift of its promoted products —
"▲ +307% units · +$576.25 revenue" — comparing the campaign window (14 days after
strategy creation) against a 28-day pre-creation baseline. DERIVED LIVE from
normalized_sales (no snapshot, no new table, no migration) → retroactive on all
existing strategies, self-correcting when data is re-uploaded.

NEW FILES:
- backend/app/services/campaign_service.py — get_campaign_performance(strategy_id,
  store_id, db): one grouped SQL aggregate per window (units+revenue per lowercased
  product name), weekly rates (baseline/4wks, campaign/elapsed-weeks), per-product +
  total lift. Status: no_baseline | measuring | complete. Lift None when baseline=0.
  revenue_lift = actual campaign revenue − baseline-predicted revenue for elapsed time.
  Windows from config: baseline_window_days=28, campaign_window_days=14.
  Honest limitation (interview): event-study method — correlation not causation,
  no control group; product matching by exact case-insensitive name.
- backend/app/schemas/campaign.py — ProductCampaignResult, CampaignPerformanceResponse.

CHANGED FILES:
- routes/ai.py — NEW GET /ai/strategies/{strategy_id}/performance (registered BEFORE
  /strategies/{strategy_id}; 404 via ValueError).
- config.py — baseline_window_days, campaign_window_days.
- frontend client.js — aiApi.performance(id).
- frontend AIStrategy.jsx — CampaignPerformance component lazy-loaded in expanded
  card: status chip (Measuring day X of N / Campaign complete), amber "early
  estimate — few days of data" chip when days_elapsed <= 3 (day-1 weekly-rate
  extrapolation inflates lift; label confidence, don't hide numbers), green/red
  totals (TrendingUp/Down), per-product rows "13/wk → 56/wk +330.8%", methodology
  footnote.
- frontend/vite.config.js — REWRITTEN (bug fix): proxy entries now use a shared
  `backend` object with bypass returning '/index.html' for requests whose Accept
  header includes text/html. Fixes hard-refresh 404s on /ai, /creative, /uploads —
  API prefixes collided with SPA page routes and the proxy swallowed document
  requests (broken since Phase 8, unnoticed). Prod unaffected (vercel.json rewrites).
- services/parsers/base_parser.py — _safe_float now rejects non-finite values
  (math.isfinite) — ROOT CAUSE FIX for the NaN bug below.
- services/analytics_service.py — _safe_float flattens NaN/inf → 0.0 (defense).
- services/campaign_service.py — _finite() guard on aggregates (defense).

═══════════════════════════════════════════════
BUGS HIT IN PHASE 12 AND FIXES (interview gold):
═══════════════════════════════════════════════
1. NaN POISONING (the big one): pandas returns empty cells as float('nan');
   float("nan") parses successfully so the parser's guard missed it; Postgres
   numeric columns ACCEPT NaN; one NaN poisons any SUM(); FastAPI's JSON encoder
   then crashes ("Out of range float values are not JSON compliant") — dashboard
   dead. Three correct systems composing into a crash far from the cause.
   Fix: validate at boundary (parser isfinite), sanitize at exit (analytics +
   campaign), repair stored damage (UPDATE ... CASE WHEN col='NaN'::numeric THEN
   NULL). Cleanup script runs via app's AsyncSessionLocal; for prod, override env:
   DATABASE_URL="<railway DATABASE_PUBLIC_URL>" python3 <<script. Prod had 0 bad rows.
2. Vite proxy swallowed SPA page refreshes (see vite.config.js above). Deeper fix
   for scale: namespace the API under /api/* so pages and endpoints can't collide.
3. Day-1 ROI numbers inflated (+307%) — small-sample extrapolation (1 day × 7);
   handled with the "early estimate" chip. Lesson: label confidence, not hide data.
Also handled: forgotten local credentials → listed users / reset password via
scripts using app's own AsyncSessionLocal + hash_password (accounts local:
test@liquoriq.com, patilkaus123@gmail.com / NewPass123 after reset; prod:
apitest@example.com / Testpass1). Vercel toolbar (visible only to logged-in team
members, never to visitors) disabled for Production in project settings.

═══════════════════════════════════════════════
GIT STATE (after Phase 12):
═══════════════════════════════════════════════
Latest commits:
  feat(phase-12): campaign ROI tracking + NaN sanitization from parser to analytics
  (earlier same phase, possibly squashed into above depending on when pushed:
   campaign ROI tracking + fix dev proxy swallowing SPA page refreshes)
  docs: Phase 11 handoff summary — price-overlay composer + Cloudinary
  fix: don't prefix absolute Cloudinary URLs in assetUrl
  42e386c feat(phase-11): price-overlay ad composer with Cloudinary storage
(plus docs commit for this handoff)

═══════════════════════════════════════════════
PHASE 13 — TO BE BUILT NEXT:
═══════════════════════════════════════════════
DISTRIBUTION AUTOPILOT — kill the last manual step: posting.
1. Meta (Instagram + Facebook) auto-posting via the Graph API:
   - Requires: Facebook Developer app, a Facebook Page + Instagram Business account
     linked to it, Page access token (long-lived), app review for
     instagram_content_publish + pages_manage_posts permissions.
   - Flow: POST final_image_url (already a public Cloudinary URL — perfect for the
     API which requires a public image URL) + instagram_caption / facebook_post.
   - Start unreviewed: works for accounts that are admins/testers of the app —
     fine for uncle's store pilot; app review only needed for arbitrary customers.
2. SMS blast via Twilio: send sms_copy to the store's customer list
   (normalized_sales has customer_phone fields — mostly empty from POS; add a
   simple customer list upload or manual entry; MUST include opt-out language,
   TCPA compliance — discuss before building).
3. "Approve to post" weekly autopilot: Monday scheduler generates strategy +
   creative; email contains Approve button (signed one-click link) → posts
   everywhere; new posts table records what went where + when (feeds Phase 12
   ROI attribution).
Design discussions first: token storage (encrypt Page tokens at rest), posting
table schema, what happens on partial failure (IG ok, FB fails).
ALSO PENDING (backlog): real product photos as ad hero, forgot-password flow,
AdvEntPOS auto-sync, margin-aware offers, per-category strategies, /api/* namespace.
FIRST VALIDATION still king: run one real campaign at uncle's store, measure lift
with Phase 12, get the case-study number for the pitch.

Start Phase 13 now, step by step. Do not skip steps. Give exact code for every file.

═══════════════════════════════════════════════
IMPORTANT — AT THE END OF PHASE 13:
═══════════════════════════════════════════════
Generate a FULL HANDOFF SUMMARY PROMPT exactly like this one — updated with Phase 13
details, every new/changed file, commands, bugs + fixes, git state, and what Phase 14
should be — one big paste-able block so the next session continues immediately.
