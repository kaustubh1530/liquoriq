═══════════════════════════════════════════════
LiquorIQ — AI AD CREATION subsystem handoff
═══════════════════════════════════════════════
This is a FEATURE handoff for the ad-creative system only. For full project
context see docs/HANDOFF_PHASE21.md.

WHAT IT DOES
An owner picks an AI strategy → generates a finished, ready-to-post ad IMAGE
(festive scene + the real/AI product + headline + exact offer price + store name
rendered in the image) plus platform copy (Instagram, Facebook, Uber Eats,
DoorDash, website banner). The owner can steer it (exact price, art-direction
instructions, format), attach a real product photo for label accuracy, and
download or (Phase 21) send the campaign.

Runs at: Frontend "Ad Creative" page (/creative). Cost ≈ $0.01 GPT-4o + ~$0.17
gpt-image-1 (quality=high) per ad, ~40-60s.

───────────────────────────────────────────────
PIPELINE (one call to generate_ad_creative does all of this)
───────────────────────────────────────────────
1. Load the strategy (scoped to the store — auth boundary).
2. GPT-4o (JSON mode) writes: platform copy fields + an "image_prompt"
   (art-direction). Inputs: occasion, products_to_promote (hero = [0]),
   recommended_offer (margin-scrubbed), store name, owner instructions, a random
   composition/lighting nudge for variety.
3. Image generation:
   - If a real product photo is available (uploaded, or auto-resolved from the
     product photo LIBRARY): gpt-image-1 images.EDIT composes the scene AROUND
     the real bottle (accurate label). Else gpt-image-1 text-to-image.
   - Size from format: square 1024x1024 / portrait 1024x1536 (A4 print) /
     landscape 1536x1024.
4. Persist PNG via storage abstraction: Cloudinary in prod (permanent CDN URL),
   local disk in dev (served at /static/creatives).
5. Save AdCreative row (image_url + all copy) and return it.

───────────────────────────────────────────────
BACKEND FILES
───────────────────────────────────────────────
app/models/ad_creative.py
  AdCreative: store_id, strategy_id, image_prompt, image_url, instagram_caption,
  facebook_post, ubereats_description, doordash_description,
  website_banner_headline, website_banner_text, model_used, created_at.
  (+ Phase 11 final_image_url / price_items columns — from the old Pillow overlay,
   now unused by the UI but still in the DB.)

app/models/product_photo.py  (Phase 16 "upload once, reuse forever")
  ProductPhoto: store_id + product_key (lowercased name, UNIQUE per store) +
  image_url. First upload for a product is saved; every future ad of that product
  auto-uses it.

app/services/creative_service.py  ← THE CORE
  - SYSTEM_PROMPT: art direction for a FINISHED festive social ad. Key rules:
    * ONE hero product only (products_to_promote[0]); no other/random bottles.
    * Render headline + CUSTOMER-FACING offer + store name IN the image.
    * NEVER render cost/margin/profit (owner-only) — enforced in prompt AND by
      _strip_internal_numbers() scrubbing the offer before it reaches the image.
    * Match palette/scene to the OCCASION (don't default to warm amber) → varied.
    * Keep ALL text inside a ~10% safe margin so nothing is cropped for print.
  - _strip_internal_numbers(offer): splits on separators, drops any clause with
    margin/cost/profit/markup/wholesale. (Was a real bug: "$89.99 (63% margin)"
    leaked onto ads.)
  - _build_user_prompt(strategy, offer_override, instructions): hero product,
    customer offer, occasion, owner instructions, random `variety` composition.
  - _to_png(bytes): normalize any uploaded photo → padded 1024 PNG for the edit API.
  - generate_ad_creative(strategy_id, store_id, db, offer_override, instructions,
    product_image_url, image_format): the pipeline above. Auto-resolves the hero
    product's library photo if none passed.

app/services/openai_service.py
  - generate_image(prompt, size): gpt-image-1 text-to-image, quality="high",
    returns PNG bytes. (Branches: legacy dall-e needs response_format/quality
    "standard"; gpt-image-1 rejects response_format and uses low/med/high.)
  - generate_image_edit(prompt, product_png, size): gpt-image-1 images.EDIT —
    composes a scene around a REAL product photo (image-to-image). Never raises;
    returns bytes.

app/services/storage_service.py
  save_image(bytes, prefix) → URL; fetch_image(url) → bytes. Cloudinary when
  CLOUDINARY_URL set (folder liquoriq/creatives, permanent secure_url), else local
  disk /static/creatives. Cloudinary SDK is sync → run via asyncio.to_thread.

app/services/compose_service.py  (Phase 11, DORMANT)
  Pillow deterministic price/text overlay on a background. Dropped from the UI when
  gpt-image-1 started rendering text well, but kept as the "print-perfect exact
  price" fallback if ever needed. Bundled fonts in app/assets/fonts (DejaVu).

app/schemas/creative.py
  GenerateCreativeRequest: strategy_id, offer_override, instructions,
  product_image_url, image_format (square|portrait|landscape). CreativeResponse.

app/routes/creative.py
  POST /creative/generate (201) — the generator.
  GET  /creative/{strategy_id} — latest creative for a strategy.
  POST /creative/product-photo (multipart, optional product_name → saves to
       library) — returns product_image_url.
  GET  /creative/product-photo?product_name= — the saved library photo, if any.
  (+ dormant compose/price endpoints from Phase 11.)

Config (app/config.py): openai_image_model="gpt-image-1", creatives_dir,
  cloudinary_url.

───────────────────────────────────────────────
FRONTEND FILES
───────────────────────────────────────────────
src/pages/Creative.jsx  (the /creative page)
  - Compact panel: Campaign select + "Price on the ad" (offer_override) on one row;
    a small Format segmented toggle (Square/Portrait/Landscape); a tiny "real photo"
    control (upload once per hero product → "on file, reused automatically"); a
    collapsible "Look & feel" textarea (instructions); Generate/Regenerate.
  - Result: the finished ad image (object-contain so portrait isn't cropped) +
    Download + the platform copy in CopyBoxes.
  - Loads the hero product's library photo on strategy select (auto-reused).

src/api/client.js — creativeApi.generate(strategyId, {offerOverride, instructions,
  productImageUrl, imageFormat}); get(strategyId); uploadProductPhoto(file,
  productName); getProductPhoto(productName).

src/pages/AIStrategy.jsx — each strategy card has a "Create ad creative →" link to
  /creative?strategy=<id> (pre-selects it).

───────────────────────────────────────────────
GOTCHAS / LESSONS (all real, all fixed)
───────────────────────────────────────────────
- gpt-image-1 replaced DALL-E 3: rejects response_format with 400; quality is
  low/med/high (NOT "standard"). Branch on model name.
- assetUrl() must pass ABSOLUTE Cloudinary URLs through unchanged; only prefix
  relative /static paths (env-parity bug — broke only in prod).
- Margin/cost must be scrubbed before reaching the image (two layers: sanitize the
  offer + instruct the model). Never trust the model to keep a secret.
- Hero-only: without an explicit "one hero, no other brands" rule the model adds
  random bottles.
- Text cropping / print: force ~10% safe margins in the prompt; use portrait
  (1024x1536) for A4; display with object-contain (not aspect-square/cover).
- Sameness: remove fixed "warm amber" palette; match palette to occasion + inject a
  random composition style each render.
- Real labels: gpt-image-1 approximates brand labels in pure generation — use the
  EDIT path with a real uploaded photo for accuracy. Scraping Google is NOT an
  option (copyright/ToS) — hence the upload-once library.
- Migrations: after any new model/column, run `alembic upgrade head` before testing
  ("column/relation does not exist" = pending migration).

───────────────────────────────────────────────
HOW TO EXTEND
───────────────────────────────────────────────
- Tune the look: edit SYSTEM_PROMPT in creative_service.py (scene/palette/text
  rules) and the `variety` list in _build_user_prompt.
- Print-perfect exact price: re-enable the Phase 11 compose_service overlay as a
  toggle (deterministic text via Pillow) for flyers.
- Meta auto-post (Phase 22 candidate): Cloudinary image_url is already a public URL,
  which the Meta Graph API requires — post image_url + a platform caption.
- New format/size: add to the image_format map in generate_ad_creative + the
  frontend toggle.
