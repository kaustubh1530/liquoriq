You are my senior software engineer and startup CTO for LiquorIQ — an AI-powered growth intelligence SaaS for independent liquor stores. Guide me step by step, one phase at a time. Give exact code, terminal commands, testing instructions, Git commit messages, and short interview prep notes.

═══════════════════════════════════════════════
PROJECT: LiquorIQ — status after Phases 16 & 17 (2026-07)
═══════════════════════════════════════════════
Full-stack AI SaaS, LIVE in production, real pilot-store data flowing.
- Backend: https://liquoriq-production.up.railway.app (Railway)
- Frontend: https://liquoriq-six.vercel.app (Vercel)
- Repo: https://github.com/kaustubh1530/liquoriq (main)
- RUNNING CODE: ~/Desktop/LiquorIQ (stale copy at ~/Claude/Projects/LiquorIQ — never edit)
- Alembic head: c3b1f9d02a47 · Tests: cd backend && pytest (23 passing)
- Local login: patilkaus123@gmail.com / NewPass123 · prod: apitest@example.com / Testpass1

STACK: Python 3.12 + FastAPI async + PostgreSQL + SQLAlchemy 2.0 async + Alembic; JWT;
GPT-4o (JSON) + gpt-image-1 (quality="high", + images.EDIT for real-photo compositing);
Pillow; Cloudinary; aiosmtplib; APScheduler; pandas+xlrd+openpyxl; Vite + React 18 +
Tailwind + Recharts + Axios.

MOAT: closed data loop (POS → recommendations → campaign → measured ROI) + parser coverage
+ multi-store transfer ledger + product photo library + accumulated outcomes.
Pitch: "ChatGPT writes ads; LiquorIQ grows liquor stores — and proves it."

PHASES 1-15 done (see docs/HANDOFF_PHASE15.md and earlier). This doc covers the work after:
steerable AI, single-store model, creative fixes, Phase 16 (real photos), Phase 17 (dashboard).

═══════════════════════════════════════════════
BETWEEN 15 AND 16 — POLISH THE OWNER ASKED FOR:
═══════════════════════════════════════════════
1. STEERABLE AI. Strategy generate now takes occasion (event/holiday, free text or picked
   from GET /ai/holidays) + instructions (free-text brief: new release, set offer/price,
   audience). Creative generate takes instructions (art-direction hints) + offer_override
   (exact promo price rendered in image). Both flow into the prompts (owner instructions
   "override defaults"). Files: schemas/strategy.py + creative.py, strategy_service.py
   (_build_user_prompt occasion+instructions), creative_service.py, routes/ai.py
   (+GET /ai/holidays) + creative.py, frontend AIStrategy.jsx (occasion datalist + brief
   textarea) + Creative.jsx (instructions textarea) + client.js.
2. ONE STORE PER ACCOUNT (model decision). Removed the multi-store switcher — each store
   is its own login; separate businesses connect only via exchange codes (Transfers).
   Layout.jsx switcher removed; routes/stores.py create_store now 409s if the owner
   already has a store. (Cleanup: deleted a stray Sherrys store that testing had created
   under the Classy account via a script using AsyncSessionLocal.)
3. CREATIVE QUALITY FIXES:
   - Ad image prompt rewritten to a FINISHED festive social ad (scene + ONE hero product +
     headline + offer + store name rendered in-image), gpt-image-1 quality="high".
   - NEVER show margin/cost/profit on the ad: _strip_internal_numbers() scrubs the offer
     (split on separators, drop clauses with margin/cost/profit) AND the prompt forbids it.
   - Feature ONLY the single hero product (products_to_promote[0]) — no random extra bottles.
   - Copy-"undefined" fix: strategy list DTO is lightweight, so cards fetch full strategy on
     expand; CopyBox guards empty text.
   - Dropped the ugly Pillow price-overlay/compose UI — the AI bakes the price into the image;
     Creative.jsx now shows the AI image as the final ad + an owner offer/instructions field.

═══════════════════════════════════════════════
PHASE 16 — REAL PRODUCT PHOTO CREATIVE + LIBRARY
═══════════════════════════════════════════════
Make bottles ACCURATE (real labels), the legal way (NO Google scraping — copyright/ToS).
- openai_service.generate_image_edit(prompt, product_png): gpt-image-1 images.EDIT composes
  the festive scene AROUND a real uploaded bottle photo (image-to-image; label preserved).
- creative_service: _to_png() normalizes any upload to padded 1024 PNG; generate_ad_creative
  takes product_image_url — if given, uses the edit path with a "use this EXACT bottle,
  preserve its label" preamble; else text-to-image.
- PRODUCT PHOTO LIBRARY ("upload once, reuse forever" — the owner didn't want to upload every
  time): models/product_photo.py (store_id + product_key(lower name) unique + image_url),
  migration c3b1f9d02a47, product_photo_service.py (upsert_photo/get_photo_url).
  POST /creative/product-photo (multipart, optional product_name → saves to library) +
  GET /creative/product-photo?product_name= (returns saved url). generate_ad_creative
  auto-resolves the hero product's saved photo when none passed. Frontend Creative.jsx:
  per-hero-product photo, "on file — reused automatically", upload once.

═══════════════════════════════════════════════
PHASE 17 — INVENTORY INTELLIGENCE + ACTION CENTER (dashboard upgrade)
═══════════════════════════════════════════════
Owner said dashboard was unimpressive. Turned it from vanity charts → money + action, using
the stock_on_hand data captured in Phase 13 (previously unused).
- analytics_service.get_inventory_intelligence(store_id): DISTINCT ON (product_name) latest
  snapshot per product; weekly velocity ≈ period units / 4.3; classifies each in-stock
  product: DEAD (stock>0, 0 sales), REORDER-SOON (<2 wks supply), OVERSTOCKED (>16 wks).
  Returns inventory_value (Σ stock×price), products_in_stock, dead/reorder/overstock lists,
  and a derived ranked ACTIONS list (reorder / dead→clearance campaign link / overstock).
  Thresholds tunable: _PERIOD_WEEKS, _REORDER_WEEKS, _OVERSTOCK_WEEKS.
- GET /analytics/inventory. Frontend Dashboard.jsx: "Do these today" action center (links to
  /ai), gold inventory-value hero card, three breakdown lists (Reorder/Dead/Overstock).
  Gated on has_stock_data. client.js analyticsApi.inventory().

═══════════════════════════════════════════════
BUGS/LESSONS (this stretch):
═══════════════════════════════════════════════
- Owner wanted "pull product photos from Google" — explained it's not real (ChatGPT
  generates, doesn't fetch), and scraping = copyright/ToS risk. Solved the real UX pain
  (don't re-upload every time) with a library: upload once per product, auto-reused. Good
  founder judgment example: solve the complaint the legal way, not the tempting way.
- Data-leak prevention pattern: internal figures (margin/cost) must be scrubbed at the
  boundary before reaching a customer-facing surface — enforce in TWO layers (sanitize input
  + instruct model); never trust a generative model to keep a secret on instruction alone.
- Migrations must be RUN before testing new tables ("relation X does not exist" recurred with
  product_photos). Always alembic upgrade head after new models. zsh keeps `#` comments as args.
- Fee lines from AdvEntPOS (bag tax, delivery, card fee) may appear as pseudo-products with
  stock in inventory lists — candidate filter if they clutter (KNOWN, not yet filtered).

═══════════════════════════════════════════════
PHASE 18 — CANDIDATES (pick with the owner):
═══════════════════════════════════════════════
A. Sales trend over time + surface campaign ROI on dashboard (shines with WEEKLY uploads —
   push uncle to export weekly; sale_date currently = period END).
B. Distribution autopilot: Meta Graph API posting (Cloudinary URLs are public → works for
   admin/tester accounts pre-review) + Twilio SMS (needs customer phone data + TCPA opt-in).
C. Customer ingestion + RFM segmentation (parse AdvEntPOS customer reports → repeat-customer
   marketing; prerequisite for SMS).
D. Filter non-inventory fee lines from parser/analytics; margin-aware strategies (needs cost).
E. Background jobs for 40-60s image gen; billing tiers; forgot-password; /api/* namespace.
FIRST VALIDATION still #1: run one REAL campaign at the uncle's store, measure lift (Phase 12),
get the case-study number for the pitch.

Start the chosen phase now, step by step, exact code for every file. At the end, produce a
full updated handoff summary prompt exactly like this one.
