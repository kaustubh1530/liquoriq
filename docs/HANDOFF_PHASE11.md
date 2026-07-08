You are my senior software engineer and startup CTO for LiquorIQ — an AI-powered growth intelligence SaaS for independent liquor stores. Guide me step by step, one phase at a time. Give exact code, terminal commands, testing instructions, Git commit messages, and short interview prep notes.

═══════════════════════════════════════════════
PROJECT: LiquorIQ
═══════════════════════════════════════════════
VISION: Store owner uploads a sales report → AI detects slow/closeout items → generates promotion strategy + a POSTABLE ad (AI background + deterministic price overlay) + platform copy for Instagram, Facebook, Uber Eats, DoorDash, website → posts in 2 minutes.

STRATEGIC MOAT: not AI creative (commodity) — the closed data loop: POS data → margin/inventory-aware recommendations → multi-channel campaign → measured ROI. Pitch: "ChatGPT writes ads; we grow liquor stores."

TECH STACK:
- Backend: Python 3.12 + FastAPI (async) + PostgreSQL + SQLAlchemy 2.0 async (asyncpg) + Alembic
- Auth: JWT (python-jose + passlib bcrypt), sessionStorage tokens
- AI: GPT-4o (JSON mode) + gpt-image-1 (NOT dall-e-3)
- Images: Pillow 10.4.0 composition + Cloudinary CDN storage (cloudinary 1.44.1)
- Email: aiosmtplib + Gmail SMTP 587; Scheduler: APScheduler (Mon 8am UTC)
- Frontend: Vite + React 18 + Tailwind + React Router + Recharts + Axios

PRODUCTION (LIVE, verified through Phase 11 on 2026-07-08):
- Backend: https://liquoriq-production.up.railway.app  (/health → database connected)
- Frontend: https://liquoriq-six.vercel.app
- Images: permanent CDN URLs at res.cloudinary.com (folder liquoriq/creatives)
- Full flow verified in prod: login → strategy → generate creative → price prefill → compose → Cloudinary URL

RUNNING CODE: ~/Desktop/LiquorIQ (a STALE copy exists at ~/Claude/Projects/LiquorIQ — never edit it).
Repo: https://github.com/kaustubh1530/liquoriq (main, PAT auth). Alembic head: e5a91b3c2d47.

═══════════════════════════════════════════════
PHASES COMPLETED (1–11):
═══════════════════════════════════════════════
1 Scaffold ✅  2 Models+migrations ✅  3 JWT auth ✅  4 Uploads ✅  5 AdvEntPOS parser ✅
6 Analytics API ✅  7 GPT-4o strategy ✅  8 React frontend ✅  9 Weekly email ✅
10 Ad creative generation + production deployment (Railway+Vercel) ✅
11 PRICE-OVERLAY AD COMPOSER + CLOUDINARY STORAGE ✅  ← just finished

═══════════════════════════════════════════════
PHASE 11 — WHAT WAS BUILT:
═══════════════════════════════════════════════
Feature: owner sets exact prices (prefilled from their own sales data) → Pillow stamps
product names + prices onto the AI background → final postable ad. No AI text typos,
no fake labels, always the real price. Plus: all images now stored on Cloudinary CDN
(Railway disk is ephemeral — this was the fix).

NEW FILES:
- backend/app/services/storage_service.py — storage abstraction (adapter pattern):
  save_image(png_bytes, prefix) → URL; fetch_image(url) → bytes.
  CLOUDINARY_URL env set → Cloudinary (uploads via asyncio.to_thread, folder
  liquoriq/creatives, returns secure_url); empty → local disk /static/creatives (dev).
  Logs "Storage backend: ..." at WARNING level (INFO is invisible in default logging).
- backend/app/services/compose_service.py — Pillow renderer. 1024x1024, rounded
  semi-transparent dark panel bottom, wrapped UPPERCASE headline (max 2 lines,
  DejaVuSans-Bold 52px), up to 5 rows "product name … $price" (price right-aligned,
  amber 250,190,88), store-name footer centered. Name truncation with ellipsis.
  Sync _render() wrapped by async render_final_ad() via asyncio.to_thread.
- backend/app/assets/fonts/DejaVuSans.ttf + DejaVuSans-Bold.ttf — bundled (deploy
  container has no system fonts; DejaVu is free-licensed).
- backend/alembic/versions/e5a91b3c2d47_...py — adds ad_creatives.final_image_url
  (String(500) nullable) + price_items (JSON nullable). down_revision c8f2a41d7e93.

CHANGED FILES:
- models/ad_creative.py — the two new nullable columns (original image_url untouched;
  regenerating/composing keeps history semantics: GET returns newest creative).
- services/creative_service.py — _save_image() removed → storage_service.save_image();
  NEW get_price_suggestions(strategy_id, store_id, db): for each products_to_promote
  name, latest NormalizedSale.unit_price (case-insensitive exact match, price None if
  no match); NEW compose_final_creative(creative_id, store_id, items, db):
  fetch_image(image_url) → render_final_ad(headline=website_banner_headline,
  items, store.name) → save_image(prefix="final") → sets final_image_url+price_items.
- schemas/creative.py — PriceSuggestion{product_name, price|None},
  PriceItem{product_name 1..200 chars, price >0 <100000}, ComposeRequest{items 1..10},
  CreativeResponse + final_image_url + price_items; protected_namespaces=() added.
- schemas/strategy.py — protected_namespaces=() on both response models (silences
  pydantic "model_used" warning).
- routes/creative.py — NEW GET /creative/{strategy_id}/prices → list[PriceSuggestion];
  NEW POST /creative/{creative_id}/compose (ComposeRequest) → CreativeResponse.
  ValueError→404/422, RuntimeError→502.
- config.py — cloudinary_url: str = "" setting.
- requirements.txt — Pillow==10.4.0, cloudinary==1.44.1 (also de-duplicated
  aiosmtplib/APScheduler lines).
- frontend/src/api/client.js — creativeApi.prices(strategyId), .compose(creativeId,
  items); assetUrl() FIXED: absolute http(s) URLs pass through untouched, only
  relative paths get API_BASE prefix (see bugs).
- frontend/src/pages/Creative.jsx — price editor panel ("Prices on the ad"): rows
  prefilled from creative.price_items or GET /prices; editable name+price inputs,
  add/remove rows, Compose/Recompose button (validRows filter, max 5 sent);
  "Final ad — ready to post" bordered card above everything with Download final PNG;
  original image demoted to "AI background (no prices)" card.

DEPLOYMENT ADDITION: Railway env var CLOUDINARY_URL = cloudinary://<key>:<secret>@<cloud>
(single connection string from the Cloudinary dashboard "API environment variable" —
paste value only, NO quotes, no "CLOUDINARY_URL=" prefix).

═══════════════════════════════════════════════
BUGS HIT IN PHASE 11 AND FIXES (interview gold):
═══════════════════════════════════════════════
1. assetUrl() prepended API_BASE to Cloudinary's ABSOLUTE URLs in prod →
   "https://...railway.apphttps://res.cloudinary.com/..." → all images invisible.
   Dev never showed it (API_BASE=''). Fix: pass through URLs starting with http.
   Lesson: environment-parity bugs live in code paths that only execute in prod —
   always smoke-test prod after deploying storage/URL changes.
2. "Storage backend" log invisible — logger.info doesn't print without logging
   config; Python's default handler shows WARNING+. Fix: log at warning (the JWT
   fingerprint line already did this — that's why it always showed).
3. User pasted `alembic upgrade head  # comment` — zsh passed "# comment" as args
   (interactive zsh doesn't treat # as comment by default) → migration silently not
   applied. Lesson: don't paste inline comments; verify the "Running upgrade" line.
4. Forgot to git push — Railway kept running old code while we looked for new log
   lines. Check `git status -sb` for "ahead" before debugging "missing" deploys.
Also: local login credentials forgotten → listed users and reset password via a
script using the app's own AsyncSessionLocal + hash_password (bcrypt is one-way).
Prod SECRET_KEY was rotated again during this phase (key_fp changed) → all prod
sessions invalidated. RULE: never touch SECRET_KEY again.

═══════════════════════════════════════════════
GIT STATE (after Phase 11):
═══════════════════════════════════════════════
Recent commits (newest first):
  fix: don't prefix absolute Cloudinary URLs in assetUrl
  fix: make storage backend log visible at default log level
  42e386c feat(phase-11): price-overlay ad composer with Cloudinary storage
  5f5cb7c docs: Phase 10 handoff summary
  21edba0 feat(phase-10): production deployment fixes
(plus docs commit for this handoff)

═══════════════════════════════════════════════
PHASE 12 — TO BE BUILT NEXT:
═══════════════════════════════════════════════
CAMPAIGN ROI TRACKING — the retention feature and the heart of the moat.
1. When a strategy is generated, snapshot baseline sales for its promoted products
   (e.g. avg weekly units + revenue over the prior 4 weeks, from normalized_sales).
2. New table campaign_results (or columns on ai_strategy_reports): baseline JSON,
   measured-at dates, status (baseline/measuring/complete).
3. After new sales data is uploaded, compute lift: same products, promo window vs
   baseline → units lift %, revenue lift $ and %.
4. Surface it: strategy card shows "▲ 31% units, +$412 revenue since campaign";
   dashboard section "Campaign performance"; weekly email includes lift lines.
5. Design decisions to discuss first: attribution window length, minimum data
   requirements, handling overlapping campaigns for the same product.
ROADMAP AFTER: Phase 13 auto-posting (Meta API) + Twilio SMS + "approve to post"
weekly autopilot; later AdvEntPOS auto-sync, margin-aware offers, compliance rules,
real product photos as hero images, forgot-password flow.
FIRST VALIDATION: run one real campaign at uncle's store (AdvEntPOS), measure lift,
turn into the pitch case study.

Start Phase 12 now, step by step. Do not skip steps. Give exact code for every file.

═══════════════════════════════════════════════
IMPORTANT — AT THE END OF PHASE 12:
═══════════════════════════════════════════════
Generate a FULL HANDOFF SUMMARY PROMPT exactly like this one — updated with Phase 12
details, every new/changed file, commands, bugs + fixes, git state, and what Phase 13
should be — one big paste-able block so the next session continues immediately.
