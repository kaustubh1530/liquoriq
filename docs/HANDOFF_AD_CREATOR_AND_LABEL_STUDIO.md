═══════════════════════════════════════════════
LiquorIQ — MODULE SPLIT: AI AD CREATOR + LABEL STUDIO
Feature handoff (supersedes docs/HANDOFF_PROFESSIONAL_CREATIVE_EDITOR.md)
═══════════════════════════════════════════════
Alembic head: **e7c93f2b1a06** · Tests: **150 passing** (cd backend && pytest -q)
Frontend deps: none added (react-konva/konva were removed — Label Studio renders
server-side now)

WHY: ad generation and badge editing had grown into one tangled feature. They are
different products with different failure modes, so they are now two independent
modules that share nothing but a base image URL.

    AI AD CREATOR                     LABEL STUDIO
    (module 1)                        (module 2)
    makes ONE finished ad             makes SHELF LABELS to print
    scene + typeset price/name        name + rating + price, no photo
    → PNG for social/print            → PNG, or a US Letter sheet

They share no code and no data. Module 2 never calls the AI.

═══════════════════════════════════════════════
MODULE 1 — AI AD CREATOR
═══════════════════════════════════════════════
RESPONSIBILITY: produce ONE beautiful, finished, ready-to-post ad. It ends there.
It does not know what a badge is.

THE FINISHED AD CONTAINS: attractive background · correct product · premium
lighting · professional composition · exact selling price · store name · headline
(+ up to 3 product details, but only when gated on — see below).

THE AI NEVER RENDERS: any text at all, and no badges/stickers/ribbons/deal labels/
discount cards/coupons/banners/seals/starbursts/price tags. The image prompt
forbids each of these by name, and there is a test asserting that.

THE TEXT LAYER, v2 (v1 made ads look "too basic" — worth understanding why):
  v1 laid a dark gradient over the LEFT HALF of every frame and typeset plain
  white text with one hard-coded red price block. Result: half the artwork was
  hidden, and every ad looked identical — a template, not a designed piece.
  v2 fixes all three causes:
    · SHOW THE PHOTO — type sits in a contained band/rail, and panels are FROSTED
      (blur + light tint of the pixels underneath) so the artwork reads through.
    · USE THE AD'S OWN COLOUR — the design plan now returns accent_color as a hex
      that the AI picks to match the scene it just art-directed. Validated by
      design_plan._accent() (hex regex, #abc expanded, junk → default) and used
      for the eyebrow, rules and price block, so each ad is coloured by its own
      plan. _readable_on() flips the price text to black on light accents.
    · LOOK ART-DIRECTED — tracked-out eyebrow kicker, hairline accent rules,
      tight leading, a real price lockup.
  FOUR LAYOUTS (owner-selectable, "auto" suits the format):
    poster — DEFAULT for square + portrait. The premium-spirits look the owner
             asked for: artwork-forward, no panel at all. A big CONDENSED cream
             headline sits straight on the photograph (only a soft top-left
             corner wash for legibility), and the offer sits in a HAND-PAINTED
             BRUSH MARK bottom-left reading OFFER / product / AT $price.
    rail   — narrow left column over a soft gradient   (alternative for portrait)
    band   — frosted band across the bottom            (alternative for square)
    banner — frosted strip on top + price medallion    (landscape / wide)

  POSTER IMPLEMENTATION NOTES:
    · _condensed() renders text to a layer and squashes it horizontally (~0.88).
      Poster headlines want a heavy condensed face and we only ship DejaVu Sans
      Bold; this is the cheap trick that gets most of the way there.
    · _brushstroke() builds the painted mark from a body rect + wavy top/bottom
      edges (overlapping ellipses) + tapered ends + dry-brush specks, blurred
      then thresholded for a crisp irregular edge. SEEDED from the price, so
      regenerating the same ad reproduces the same mark rather than a new blob.
      A rounded rectangle here reads as a UI button; the painted edge reads as
      art direction — that difference is the whole point.
    · _corner_wash() fades out both right and down from the top-left, ~40% the
      strength of the v1 scrim. Enough for legibility, not a blanket.
    · Brush ink flips to dark on light accents (cream on gold is unreadable).
    · Headline starts at 7.5% from the top — the owner's original complaint was
      a clipped headline, and there is a test asserting row 0 stays untouched.

  TWO BUGS FOUND ON THE FIRST REAL GENERATION (both now regression-tested):
    1. TEXT RAN OVER THE BOTTLE. _fit_block only checked "were any words
       dropped", so a single long word ("CELEBRATION") was never caught and
       rendered at full 117px — 794px wide in a 573px column. It now asserts
       EVERY line fits the width. Same headline now sets at 83px.
    2. THE PRICE SLOT HELD THE PRODUCT NAME. strategy.recommended_offer is a
       SENTENCE ("Lamarca Prosecco 750ml for $21.99 this weekend"); capping it
       to 24 chars produced "Lamarca Prosecco 750ml…" where the price belonged,
       and the ad then showed the product twice. design_plan.extract_price()
       now pulls the actual deal — $21.99 · 20% OFF · BOGO · 2 FOR $30 ·
       BUY 2 GET 1 FREE — and falls back to a short phrase only when the offer
       contains no deal at all. is_amount() decides whether "AT" prefixes it,
       because "AT 20% OFF" doesn't read.
    Also: the brush mark is clamped to 42% of the frame so it stops short of the
    product, and long product names SHRINK to fit rather than truncating to
    "LAMARCA…".
  Headlines NEVER truncate silently: _fit_block shrinks while any word is being
  dropped, and only marks an ellipsis when it genuinely cannot fit.

HOW TEXT GETS ON THE AD (the key design decision):
  gpt-image-1 is unreliable at typography — it crops words and misspells prices.
  So the model paints the SCENE ONLY, and the SERVER typesets the words:
    1. GPT-4o → structured design_plan (art direction + headline + details)
    2. design_plan.validate_design_plan() → deterministic scrub/caps/fact-gating
    3. compose_image_prompt() → scene + product, NO text, NO badges
       (prompt asks the model to keep the LEFT THIRD calm for the caption)
    4. gpt-image-1 renders the scene (edit path if a real product photo exists)
    5. ad_text_renderer.render_ad_text() → Pillow stamps headline / subheadline /
       EXACT price / product details / store name onto a soft left-to-right scrim
    6. save_image() → the finished ad
  Result: the price is always exactly what the owner typed, nothing is ever
  cropped or misspelled, and the layout is identical every time.

PRODUCT-DETAIL GATING (design_plan.show_product_details):
  Details appear ONLY when the owner ticks "Show product details", OR the
  campaign type is one of: new_arrival · product_spotlight · premium_collection ·
  limited_edition. Every other campaign stays clean and minimal.
  Details are still fact-gated: any claim about proof/age/award/origin/ingredients
  is dropped unless it appears in the store's confirmed ProductFacts.

FILES (module 1):
  backend/app/services/design_plan.py       — REWRITTEN. Plan validation, gating,
      compose_image_prompt (no text/no badges), ad_text_spec() hand-off.
      badge_texts from the AI are DISCARDED on purpose.
  backend/app/services/ad_text_renderer.py  — NEW. Pillow caption rail: scrim,
      auto-shrinking headline, subheadline, price block, bulleted details,
      store name above a hairline rule. Ratio-based so all 3 formats look right.
  backend/app/services/creative_service.py  — rewired to the 6-step pipeline;
      SYSTEM_PROMPT now art-directs the PHOTOGRAPH only; design_json left NULL.
  backend/app/routes/creative.py            — label endpoints REMOVED (they moved
      to module 2). Now: generate, product-facts, prices, compose, get.
  backend/app/schemas/creative.py           — + campaign_type, show_product_details;
      SaveDesignIn/ExportIn removed.
  frontend/src/pages/Creative.jsx           — "AI Ad Creator". Campaign-type
      selector, product-details opt-in, and an "Add labels" button that hands the
      ad to Label Studio. The embedded editor is GONE.

═══════════════════════════════════════════════
MODULE 2 — LABEL STUDIO (shelf labels)
═══════════════════════════════════════════════
RESPONSIBILITY: SHELF LABELS — the small printed card a store clips to the shelf
edge: bottle name, rating, price. No product photo, no ad image. It never calls
the AI and shares nothing with module 1.

A LABEL IS A LIST OF POSITIONED ELEMENTS (text, price, art, starburst, banner,
line). Everything can be dragged, resized, recoloured, rotated, duplicated or
deleted, and any number of art pieces can be added. Positions are RELATIVE
(0..1 of the card), so a label designed at 4×3″ still works at 5×7″.

TWO DESIGN DECISIONS:
 1. STYLES ARE STARTING POINTS, NOT CAGES. An earlier version laid everything
    out for you — tidy, but the owner had no freedom ("I should be able to move
    the text and art and price"). Style presets now GENERATE a good set of
    elements; nothing is locked afterwards. POST /label-studio/from-style is
    that "start me off" path.
 2. THE SERVER DRAWS THE PREVIEW **AND REPORTS THE BOXES**. POST
    /label-studio/preview returns a scaled PNG plus each element's box in
    relative units. The browser places its drag handles from those boxes, so the
    hit areas line up exactly with the print. One renderer, one geometry — no
    second layout engine in the browser to drift out of sync. (react-konva is
    still gone; the drag surface is plain absolutely-positioned divs.)

ART CATALOGUE (11, all drawn with Pillow — emoji are impossible, the print fonts
have no emoji glyphs): bottles · bottle · barrel · grapes · wineglass · martini ·
beer · star · laurel · flourish · snowflake. Each declares an `aspect` so the
renderer can derive height from the dragged width.

DATA MODEL: label_designs (c9f42a17d3e5, reshaped by d1a58b04e7c3)
  store_id (CASCADE) · creative_id (SET NULL, optional provenance) · name ·
  base_image_url (NOW NULLABLE — shelf labels draw their own background) ·
  final_image_url (NULL until export) · design_json = the label spec:
    {size, theme, icon, product_name, price, was_price, tagline,
     details[≤3], rating:{kind,value,source}, show_border}

MODELLED ON THE STORE'S OWN CANVA LABELS (the owner sent photos of real ones).
  The house style is NOT what a designer would guess:
    · SERIF type, not sans — traditional, price-list looking. DejaVu Serif and
      Liberation Serif are now bundled alongside DejaVu Sans (all freely
      licensed) because the deploy container has no system fonts.
    · Black on white paper. Colour is used sparingly: a red sale price, a red
      starburst, a red banner.
    · The bottle SIZE ("750ML") tucked in a corner.
    · "REGULAR: $36.99" and "SAVE $4 !" spelled out under the sale price.
    · Small bottle/barrel clip-art in the bottom corners.

THREE STYLES, one per real label they print:
  classic      — name on top, starburst badge, huge price, REGULAR + SAVE
                 (their Woodford tag)
  price_first  — big red price on top, name below, red banner at the foot
                 (their Traveller tag)
  deal_bookend — vertical D-E-A-L columns down both edges, content centred,
                 store name at the foot (their Monte Alto tag)
  style_fields() tells the UI which optional fields each style uses, so the form
  stays short instead of showing every control for every style.

"SAVE $4 !" IS COMPUTED, not typed — sl.savings() parses both prices and returns
  "" unless there is a genuine saving. fmt_money() drops pointless cents ($4, not
  $4.00) to match how they write it. This is small but it is exactly the kind of
  arithmetic worth doing for a busy owner.

SAVED STYLES (templates): as_template() keeps the LOOK and blanks the product
  fields; apply_template() puts new content into that look. A template is just a
  LabelDesign row with is_template=true (migration e7c93f2b1a06) — no second
  table. NOTE: a template necessarily stores show_regular/show_save as false
  (it has no prices), so apply_template RE-ENABLES them when the incoming
  content has a regular price. A test covers this; without it, applying a style
  silently hid the SAVE line.

SIZES (300 DPI): small 3.5×2″ · medium 4×3″ · wide 5×3″ · large 5×7″.
FONTS: serif (DejaVu, default) · serif_alt (Liberation/Times) · sans.
ACCENTS: sale red · all black · green · navy.  ART: bottles · barrel · both · grapes.

PRINT SHEET: select any saved labels → US Letter PDF at 300 DPI, auto-paginated,
  with light grey cut guides. All labels on a sheet share one size so the grid
  cuts cleanly.

POS PREFILL (the moat, applied to a mundane task): GET /label-studio/products
  returns the store's best sellers with the latest price from their OWN sales
  data, so picking a bottle fills in the name and price. No generic label maker
  can do that.

FILES (module 2):
  backend/app/services/shelf_label.py           — NEW (sizes/themes/icons/validation, pure)
  backend/app/services/shelf_label_renderer.py  — NEW (Pillow label + sheet PDF)
  backend/app/services/label_design_service.py  — REWRITTEN (store-scoped DB ops + prefill)
  backend/app/models/label_design.py            — base_image_url now nullable
  backend/app/schemas/label_studio.py           — REWRITTEN
  backend/app/routes/label_studio.py            — REWRITTEN
  backend/alembic/versions/d1a58b04e7c3_shelf_labels.py — NEW
  frontend/src/pages/LabelStudio.jsx            — REWRITTEN (fields + live preview)
  DELETED: services/label_studio.py (badge templates), pages/labelstudio/* (konva)

ROUTES (all store-scoped):
  GET    /label-studio/templates          — saved styles
  POST   /label-studio/templates          — save the current look as a style
  POST   /label-studio/templates/{id}/apply — put your product in that style
  DELETE /label-studio/templates/{id}
  GET    /label-studio/options            — styles, sizes, fonts, accents, art
  GET    /label-studio/products           — POS prefill
  POST   /label-studio/preview            — live PNG of an unsaved spec
  GET    /label-studio/labels             — saved labels
  POST   /label-studio/labels             — create
  GET    /label-studio/labels/{id}        — reopen
  PUT    /label-studio/labels/{id}        — save edits
  POST   /label-studio/labels/{id}/export — render + store a PNG
  DELETE /label-studio/labels/{id}
  POST   /label-studio/sheet              — printable US Letter PDF

═══════════════════════════════════════════════
NAVIGATION
═══════════════════════════════════════════════
Dashboard · Uploads · AI Strategy · 🎨 AI Ad Creator · 🏷️ Label Studio ·
Transfers · Customers   (Campaigns/Inventory/Marketing/Settings are future items)

═══════════════════════════════════════════════
TESTS
═══════════════════════════════════════════════
tests/test_design_plan.py (15) — scrub, caps, owner-controlled offer, the four
  campaign types gating details, owner opt-in, dedupe/cap/no-hero-name, fact
  grounding, prompt forbids ALL text, prompt forbids each badge word by name,
  background stays rich, ad_text_spec carries the exact price, spec has no
  badge-shaped fields, AI badge_texts discarded.
tests/test_label_studio.py (28) — print sizes sane, every theme has every colour
  the renderer reads, renderer/catalogue icon sets agree, unknown size/theme/icon
  fall back, validation never raises on 6 kinds of garbage, PRICE PRESERVED
  EXACTLY, truncation not dropping, tagline uppercased, details capped + deduped,
  stars snap to halves + clamp, points clamp, rating NaN rejected, "none" zeroes
  out, unknown kind falls back; renders every theme × size, renders when totally
  empty, crowded label still fits the card, all icons draw, stars and points both
  render; labels_per_page is size-dependent, sheet paginates and is a real PDF,
  single-label sheet works, label_summary.

═══════════════════════════════════════════════
RUN / TEST / SHIP
═══════════════════════════════════════════════
  # 1. delete superseded files (dead code / stale tests)
  rm ~/Desktop/LiquorIQ/backend/tests/test_design_overlay.py
  rm ~/Desktop/LiquorIQ/backend/app/services/label_studio.py
  rm -rf ~/Desktop/LiquorIQ/frontend/src/pages/creative
  rm -rf ~/Desktop/LiquorIQ/frontend/src/pages/labelstudio
  # react-konva is no longer used anywhere:
  cd ~/Desktop/LiquorIQ/frontend && npm uninstall react-konva konva

  # 2. backend
  cd ~/Desktop/LiquorIQ/backend && source venv/bin/activate
  alembic upgrade head        # → d1a58b04e7c3
  pytest -q                   # → 96 passed
  uvicorn app.main:app --reload

  # 3. frontend  (restart it — vite.config.js changed, hot reload won't pick it up)
  cd ~/Desktop/LiquorIQ/frontend && npm install && npm run dev

  # 4. verify: AI Ad Creator → pick a campaign type → Generate (needs OpenAI
  #    credits). The ad should have a crisp headline + exact price + store name
  #    and NO badges. Then Label Studio → pick one of your products → set a
  #    rating → Save → tick a few labels → Print.

  git add -A
  git commit -m "refactor(creative): split into AI Ad Creator + Label Studio modules

AI Ad Creator now owns only the advertisement: the model paints the scene and
Pillow typesets the headline, exact price and store name, so text is never
cropped or misspelled. Product details are gated behind campaign type or an
explicit owner opt-in. The image prompt forbids all text and every badge form.

Label Studio is a new independent module (label_designs table, 20 starter
templates, 10 shapes, snap guides, layers, undo/redo) that composites labels on
top of an untouched base image and flattens only on export."
  git push origin main

═══════════════════════════════════════════════
INTERVIEW NOTES
═══════════════════════════════════════════════
- SEPARATION OF CONCERNS, concretely: two features had merged because they shared
  a canvas. Splitting them by RESPONSIBILITY (make the ad vs. decorate the ad)
  rather than by technology gave each an independent data model, route namespace,
  and failure mode. The only coupling left is a base image URL.
- "DON'T FIGHT THE TOOL": generative image models are unreliable at exact text, so
  we removed text from the model's job and typeset it deterministically.
  Correctness by construction, not by prompt-tuning.
- TRUST BOUNDARIES: the LLM is untrusted (scrub margins, gate factual claims,
  discard badges) and so is the browser (validate_design clamps, de-NaNs, caps and
  de-duplicates rather than throwing). Neither can produce a 500 or leak internals.
- LATE FLATTENING: keeping labels as data until export is what makes reopen-to-edit
  free — no AI regeneration, no re-spend, full fidelity.
- NON-DESTRUCTIVE MIGRATION: ad_creatives.design_json is left in place though the
  new code ignores it, so the deploy is trivially reversible.

FOLLOW-UPS (deliberately deferred): icon/emoji picker, image + custom SVG upload,
group/ungroup, polygon shape, reusable owner-saved presets (label_presets table),
multi-select, per-label margin.
