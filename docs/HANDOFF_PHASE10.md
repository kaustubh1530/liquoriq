You are my senior software engineer and startup CTO for LiquorIQ — an AI-powered growth intelligence SaaS for independent liquor stores. Guide me step by step, one phase at a time. Give exact code, terminal commands, testing instructions, Git commit messages, and short interview prep notes.

═══════════════════════════════════════════════
PROJECT: LiquorIQ
═══════════════════════════════════════════════
VISION: Store owner uploads a sales report → AI detects slow/closeout items → generates promotion strategy + actual ad creative (image + copy) for Instagram, Facebook, Uber Eats, DoorDash, website → store owner posts in 2 minutes.

STRATEGIC DIRECTION (decided end of Phase 10): the moat is NOT AI creative (commodity) — it is the closed data loop: POS data → margin/inventory-aware recommendations → multi-channel campaign → measured ROI ("this promo lifted units 31%, +$412"). Pitch: "ChatGPT writes ads; we grow liquor stores."

TECH STACK:
- Backend: Python 3.12 + FastAPI (async) + PostgreSQL + SQLAlchemy 2.0 async (asyncpg) + Alembic
- Auth: JWT (python-jose + passlib bcrypt), token in sessionStorage on frontend
- AI: OpenAI GPT-4o with JSON mode + **gpt-image-1** for images (NOT DALL-E 3 — see bugs)
- Email: aiosmtplib + Gmail SMTP (STARTTLS 587)
- Scheduler: APScheduler AsyncIOScheduler (weekly cron, Monday 8am UTC)
- Frontend: Vite + React 18 + Tailwind + React Router + Recharts + Axios
- Pydantic v2 + pydantic-settings

PRODUCTION (LIVE as of 2026-07-07):
- Backend: https://liquoriq-production.up.railway.app (Railway, us-west2)
- Frontend: https://liquoriq-six.vercel.app (Vercel)
- /health returns {"status":"healthy","database":"connected"}
- Full flow verified in prod: register → store → upload → parse → analytics → strategy → ad creative → weekly email

FOLDER STRUCTURE (~/Desktop/LiquorIQ/ is the RUNNING project — a stale copy exists at ~/Claude/Projects/LiquorIQ, do NOT edit that one):
backend/
  Procfile              ← web: until alembic upgrade head; do sleep 5; done && uvicorn --host 0.0.0.0 --port $PORT
  .python-version       ← 3.12 (pins Railway build)
  app/
    config.py           ← pydantic-settings; NEW: frontend_url (CORS), openai_image_model="gpt-image-1",
                          creatives_dir="generated_images", field_validator that rewrites
                          postgresql:// and postgres:// → postgresql+asyncpg:// (Railway compat)
    database.py         ← async engine + AsyncSessionLocal + get_db (commit/rollback wrapper)
    main.py             ← lifespan (scheduler), CORS uses ["*"] in debug else [frontend_url],
                          NEW: StaticFiles mount /static/creatives → generated_images/,
                          NEW: creative router at /creative
    scheduler.py        ← APScheduler weekly_growth_report (Mon 8am UTC)
    models/
      user.py, store.py, uploaded_report.py (NOT upload.py), normalized_sale.py, ai_strategy_report.py
      ad_creative.py    ← NEW Phase 10: AdCreative — id, store_id FK, strategy_id FK(ai_strategy_reports,
                          CASCADE, indexed), image_prompt, image_url ("/static/creatives/<uuid>.png"),
                          instagram_caption, facebook_post, ubereats_description, doordash_description,
                          website_banner_headline, website_banner_text, model_used, created_at.
                          Regeneration inserts a new row (history kept); GET returns newest.
    schemas/
      user.py, token.py (NOT auth.py), upload.py, analytics.py, strategy.py
      creative.py       ← NEW: GenerateCreativeRequest{strategy_id}, CreativeResponse (all columns)
    routes/
      auth.py           ← /auth/register /auth/login /auth/me; get_current_user dependency
      stores.py         ← /stores (POST), /stores/me (GET/PUT); get_current_store dependency
      uploads.py        ← /uploads/report (POST multipart), /uploads, /uploads/{id}, /uploads/{id}/parse
      analytics.py      ← summary, top-products, slow-products, category-performance, channel-performance
      ai.py             ← /ai/generate-promotion (201), /ai/strategies, /ai/strategies/{id}
      creative.py       ← NEW: POST /creative/generate (201, 15-60s), GET /creative/{strategy_id}
                          (latest; 404 if none). ValueError→404/422, RuntimeError→502.
      reports.py        ← /reports/send-weekly, /reports/send-weekly-all
    services/
      openai_service.py    ← generate_json_response(system,user)→dict (GPT-4o JSON mode);
                             NEW generate_image(prompt,size)→PNG bytes: builds kwargs dict, only adds
                             response_format="b64_json"+quality="standard" if model startswith("dall-e")
                             because gpt-image-1 rejects response_format (400) and always returns b64
      creative_service.py  ← NEW: pipeline = load strategy (scoped to store) → GPT-4o generates platform
                             copy AND the image_prompt (JSON, validated against REQUIRED_FIELDS) →
                             generate_image() → save PNG to creatives_dir with uuid4 name →
                             insert AdCreative row. System prompt has per-platform rules + alcohol-ad
                             guardrails + "no text/faces/brands in image" (gpt-image-1 sometimes renders
                             fake labels anyway — Phase 11 fixes this properly with overlays)
      strategy_service.py  ← GPT-4o promotion strategy pipeline (Phase 7)
      analytics_service.py, report_service.py (has NaN sanitizers), email_service.py, parse_service.py
      parsers/adventpos_parser.py
    utils/security.py   ← bcrypt + JWT create/decode; NEW: logs "JWT config loaded: alg=… key_fp=…"
                          (sha256 fingerprint, first 10 chars) at import, and logs JWTError reason on
                          decode failure — KEEP THESE, they solved a production auth outage
  alembic/versions/     ← chain: 00adbf8fc6c9 → 929b146fe2d4 → 0f13d0315602 → 4a5ead59118f →
                          a57934a141b2 → c8f2a41d7e93 (NEW: ad_creatives table)
  alembic/env.py        ← NEW: imports app.models.ad_creative for autogenerate
frontend/
  vercel.json           ← NEW: SPA rewrite {"source":"/(.*)","destination":"/index.html"}
  vite.config.js        ← proxy now includes /creative /static /reports (+ existing 5)
  index.html            ← title set to "LiquorIQ — AI Growth Intelligence for Liquor Stores"
  src/
    api/client.js       ← NEW: export API_BASE = import.meta.env.VITE_API_URL ?? '' ;
                          axios baseURL = API_BASE || '/' ; export assetUrl(path)=`${API_BASE}${path}`
                          (for <img src> of generated images); NEW creativeApi = {
                          generate:(id)=>post('/creative/generate',{strategy_id:id}),
                          get:(id)=>get(`/creative/${id}`) }
    pages/
      Login.jsx, Register.jsx, Dashboard.jsx, Uploads.jsx
      AIStrategy.jsx    ← (NOT Strategy.jsx) NEW: each expanded card has
                          <Link to={`/creative?strategy=${s.id}`}> "Create ad creative →"
      Creative.jsx      ← NEW Phase 10: strategy <select> (preselects ?strategy= query param, else
                          newest), auto-loads existing creative via GET (404 = none), Generate/
                          Regenerate button (15-60s), image card with Download PNG (assetUrl),
                          6 CopyBox components (Instagram/Facebook/UberEats/DoorDash/banner headline+
                          text) with one-click clipboard copy
    App.jsx             ← NEW route /creative (protected)
    components/Layout.jsx ← NEW nav item { to:'/creative', label:'Ad Creative', icon:Megaphone }

STARTUP (local dev):
  T1: cd ~/Desktop/LiquorIQ/backend && source venv/bin/activate && uvicorn app.main:app --reload
  T2: cd ~/Desktop/LiquorIQ/frontend && npm run dev
  http://localhost:5173, API docs http://localhost:8000/docs

DEPLOYMENT CONFIG (already done, for reference):
Railway backend service: Root Directory=backend, builder=Railpack, domain port 8080.
Variables: DATABASE_URL (= value of Postgres DATABASE_PUBLIC_URL — private networking refused
connections, see bugs), OPENAI_API_KEY, OPENAI_MODEL=gpt-4o, SECRET_KEY (64-char hex, NO QUOTES),
DEBUG=false, APP_ENV=production, SMTP_USER, SMTP_PASSWORD, FROM_EMAIL, FRONTEND_URL=
https://liquoriq-six.vercel.app, RAILPACK_PYTHON_VERSION=3.12, NIXPACKS_PYTHON_VERSION=3.12.
Vercel: Root Directory=frontend, framework Vite, env VITE_API_URL=https://liquoriq-production.up.railway.app.
NOTE: generated_images/ on Railway is EPHEMERAL — images are lost on redeploy unless a Volume is
mounted at /app/generated_images (recommended; or move to S3/Cloudinary in Phase 11).

═══════════════════════════════════════════════
PHASES COMPLETED (1–10):
═══════════════════════════════════════════════
Phase 1 — Scaffold (FastAPI + Vite + PostgreSQL + Alembic) ✅
Phase 2 — DB models + migrations ✅
Phase 3 — JWT auth ✅
Phase 4 — File uploads ✅
Phase 5 — AdvEntPOS parser → NormalizedSale ✅
Phase 6 — Analytics API ✅
Phase 7 — GPT-4o promotion strategy ✅
Phase 8 — React frontend ✅
Phase 9 — Weekly email report (NaN fix committed) ✅
Phase 10 — Ad creative generation + PRODUCTION DEPLOYMENT ✅
  Cost per creative ≈ $0.05 (1 GPT-4o call + 1 gpt-image-1 image).
  Design: GPT-4o writes the DALL-E-style image_prompt itself (saved to DB for audit/reproducibility);
  b64 response persisted to disk because image URLs from OpenAI expire in ~1h.

═══════════════════════════════════════════════
BUGS HIT IN PHASE 10 AND THEIR FIXES (interview gold):
═══════════════════════════════════════════════
1. OpenAI 400 "Unknown parameter: 'response_format'" — OpenAI replaced DALL-E 3 with gpt-image-1,
   which always returns b64 and rejects the legacy param. Fix: default model gpt-image-1; only send
   response_format/quality when configured model starts with "dall-e". Lesson: capability-branch on
   model, provider APIs change server-side regardless of pinned SDKs.
2. Railway build failed compiling pandas — builder used Python 3.13 (no wheels for pinned pandas
   2.2.2/asyncpg 0.29). Fix: backend/.python-version=3.12 + RAILPACK_PYTHON_VERSION var + pandas 2.2.3.
   Lesson: pin the runtime, not just packages.
3. Alembic crash "Connect call failed 127.0.0.1:5432" — DATABASE_URL not set → fell back to dev
   default. Fix: set variables. Then "Could not parse SQLAlchemy URL from ''" — the ${{Postgres.DATABASE_URL}}
   reference didn't resolve. Then connection refused on postgres.railway.internal — private networking
   flaky. Final fix: paste DATABASE_PUBLIC_URL value directly. The config field_validator rewrites
   postgresql:// → postgresql+asyncpg:// so any PaaS URL format works.
4. Boot race: backend migrated before Postgres was ready; first Procfile retry loop had a logic bug
   that started uvicorn even after 6 failed attempts. Fix: `until alembic upgrade head; do sleep 5; done`
   — server cannot start unmigrated.
5. THE BIG ONE — JWT "Signature verification failed" on tokens the server itself issued.
   Root cause: SECRET_KEY was pasted into Railway WITH surrounding double quotes; the quotes became
   part of the key ("..."). Local .env parsers strip quotes, platform UIs don't. Mixed-key states
   across redeploys made login/verify disagree. Debugged by: logging sha256 key fingerprints at
   startup, logging JWTError reasons, and offline HMAC-verifying a captured token against candidate
   key variants (quoted variant matched). Fix: openssl rand -hex 32, pasted with no quotes.
   Lesson: never log secrets — log fingerprints; verify signatures offline to identify signing keys.
6. Weekly report email "not received" — it was sent to the logged-in owner's email, which was a fake
   test address. Works when triggered as a real account.

Also known/minor: pydantic UserWarning "model_used conflicts with protected namespace model_" —
harmless; silence in Phase 11 with model_config["protected_namespaces"] = ().

═══════════════════════════════════════════════
GIT STATE:
═══════════════════════════════════════════════
Remote: https://github.com/kaustubh1530/liquoriq.git (main, PAT auth). Working tree clean except
possibly backend/app/services/report_service.py.bak (untracked junk — delete).
Recent commits (newest first):
  21edba0 feat(phase-10): production deployment fixes (Python pin, DB retry, JWT diagnostics)
  6701b4d debug: log JWT failure reason and secret-key fingerprint
  dd03e11 chore: set production page title
  8695330 fix(deploy): retry migrations until Postgres is ready
  b88243d fix(deploy): pin Python 3.12 for Railway build (match local env)
  c5cb1a4 fix: update pandas for Railway Python 3.13 build
  03ff335 chore(phase-10): production config for Railway + Vercel deployment
  4a61bfa feat(phase-10): DALL-E 3 ad creative generation with platform-specific copy

═══════════════════════════════════════════════
PHASE 11 — TO BE BUILT NEXT:
═══════════════════════════════════════════════
Goal: PRICE-OVERLAY AD EDITOR — make creatives accurate, postable, and price-driven.
1. Prefill each promoted product's price from normalized_sales.unit_price; owner edits promo price
   in a small panel on Creative.jsx.
2. Pillow (backend) composes final ad: AI/template background + deterministic text overlay of product
   names and EXACT prices (no AI typos, no fake labels). Store composed PNG alongside original.
3. Optional: owner uploads a real product/shelf photo to use as the hero image.
4. Move image storage to S3 or Cloudinary (fixes Railway ephemeral disk).
5. Cleanup: silence pydantic protected-namespace warning; delete report_service.py.bak.

ROADMAP AFTER (agreed strategy):
- Phase 12: campaign ROI tracking — snapshot baseline sales of promoted SKUs at strategy creation,
  compare after 2-4 weeks, show lift in dashboard + weekly email. THE retention feature.
- Phase 13: auto-posting (Meta API for IG/FB), SMS via Twilio; "approve to post" weekly autopilot.
- Later: AdvEntPOS auto-sync, margin-aware offers (needs cost data), per-category strategies
  (uncle's store has ~15,000 SKUs — analytics handle it fine; AI gets top-N slow movers only),
  state alcohol-ad compliance rules in prompts.
- FIRST VALIDATION: run one real campaign at uncle's store (AdvEntPOS), measure lift manually,
  turn it into the case study for the pitch.

Start Phase 11 now, step by step. Do not skip steps. Give exact code for every file.

═══════════════════════════════════════════════
IMPORTANT — AT THE END OF PHASE 11:
═══════════════════════════════════════════════
Generate a FULL HANDOFF SUMMARY PROMPT exactly like this one — updated with Phase 11 details, every
new/changed file, commands used, bugs + fixes, git status, and what Phase 12 should be — as one big
paste-able block so the next session can continue immediately.
