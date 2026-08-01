═══════════════════════════════════════════════
LiquorIQ — PROFESSIONAL AD UPGRADE + EDITABLE LABEL CREATOR
Feature handoff (supersedes docs/HANDOFF_AD_CREATIVE.md for the creative pipeline)
═══════════════════════════════════════════════
GOAL: professional-quality ads + a reusable, editable label/badge creator. Being
built in SLICES. SLICE 1 (design-plan pipeline) and SLICE 2 (background-only images
+ react-konva editor + two-stage UX) are BOTH SHIPPED.

DESIGN DECISION (from reference-image analysis): professional ads are COMPOSED,
not painted. The AI makes a beautiful BACKGROUND + PRODUCT; crisp TEXT / PRICE /
BADGES are rendered deterministically on top. Chosen editor tech = REACT-KONVA
(declarative React components → labels live in state, serialize to JSON, easy
undo/redo & reopen-to-edit; Fabric.js is imperative and fights React).

Target flow: owner brief + product facts → AI structured DESIGN PLAN → deterministic
validation → AI background/product image → editable react-konva overlay → export →
Cloudinary + design JSON (reopen & edit without regenerating).

═══════════════════════════════════════════════
SLICE 1 — SHIPPED (design-plan pipeline + product facts + persistence foundation)
═══════════════════════════════════════════════
Alembic head: b7e3f1a06c92 · Tests: 61 passing (cd backend && pytest).

NEW: app/services/design_plan.py (PURE, tested)
  - validate_design_plan(plan, hero, customer_offer, product_facts): scrubs
    internal terms (margin/cost/profit/markup/wholesale) from EVERY field; caps
    headline/subheadline/badge/supporting lengths; supporting_blocks ≤3, deduped,
    no hero-name repeat; DROPS unsupported factual claims (proof/age/award/origin/
    ingredient) unless present in confirmed product_facts; forces the owner's exact
    offer text. Never raises.
  - compose_image_prompt(plan, store_name, background_only): builds the gpt-image-1
    prompt from the VALIDATED plan — pro composition (one focal point, price in a
    high-contrast shape 3-4x body, ≤3 supporting blocks, quiet themed bg, safe
    margins, disciplined palette). background_only=True → NO text in the image
    (for the editor slice). Currently called with background_only=False (interim:
    still renders text so ads aren't blank before the editor ships).
  - initial_design_json(plan, store_name, image_url): builds the editable overlay
    (canvas, source_image, labels[] for headline/offer/badges/support/store) with
    DETERMINISTIC text — the seed for the react-konva editor.

CHANGED: app/services/creative_service.py
  - SYSTEM_PROMPT now returns a STRUCTURED design_plan (headline, subheadline,
    palette, typography, product/offer placement, supporting_blocks, badge_texts,
    background, lighting, composition) + platform copy. FACTS RULE in prompt: use
    ONLY provided facts, never invent proof/ABV/age/award/origin/size.
  - _build_user_prompt(strategy, offer_override, instructions, product_facts):
    passes confirmed facts (or "None provided — DO NOT invent").
  - _validate_creative requires design_plan (dict) + copy fields.
  - generate_ad_creative(..., product_facts): validates plan → composes prompt →
    generates image (edit path if real photo) → saves image_prompt, design_plan,
    design_json. Auto-resolves the hero product's saved photo AND saved facts if
    not passed (reuse, like the photo library).

NEW: app/models/product_facts.py (ProductFacts: store_id + product_key UNIQUE +
  category + facts JSON) — "confirm once per product, reuse forever."
  app/services/product_facts_service.py (upsert_facts / get_facts).
CHANGED: app/models/ad_creative.py — + design_plan JSON, + design_json JSON (both
  nullable → old creatives valid).
Migration b7e3f1a06c92: product_facts table + ad_creatives.design_plan/design_json.

ROUTES (app/routes/creative.py):
  - POST /creative/generate now accepts product_facts (in GenerateCreativeRequest).
  - GET  /creative/product-facts?product_name= → saved facts.
  - POST /creative/product-facts {product_name, category, facts} → upsert (reusable).
  - PUT  /creative/{creative_id}/design {design_json} → save the editable overlay
    (reopen & edit without regenerating). CreativeResponse now returns design_plan +
    design_json.

FRONTEND (Creative.jsx + client.js):
  - "Product details (optional)" collapsible: category + "label: value" lines
    (proof/age/origin/tasting notes…). Saved as reusable facts and passed to
    generation; loaded for the hero product on select. Note states the AI uses ONLY
    confirmed facts, never invents.
  - creativeApi: getFacts, saveFacts, saveDesign, generate(...productFacts).

TESTS: tests/test_design_plan.py (8): internal-term scrub everywhere, length caps,
  offer is owner-controlled, supporting-block cap/dedupe/no-product-name, unsupported
  claims dropped without facts / kept with facts, background_only prompt has no text,
  with-text prompt has price+store+scrub rule, initial_design_json builds labels.

RUN / TEST / SHIP (slice 1):
  cd ~/Desktop/LiquorIQ/backend && source venv/bin/activate
  alembic upgrade head          # → b7e3f1a06c92 (product_facts + design columns)
  pytest -q                     # → 61 passed
  uvicorn app.main:app --reload
  # AI Strategy → Create ad creative → (optional) Product details → Generate.
  git add -A && git commit -m "feat(creative): professional design-plan pipeline + validation + reusable product facts + design persistence"
  git push origin main

INTERVIEW NOTES:
  - Plan-then-render: ask the LLM for a STRUCTURED plan, validate it deterministically,
    then compose the image prompt from the clean plan → control + testability, and no
    hallucinated facts / leaked margins reach the ad.
  - Facts-grounding: confirmed facts gate factual claims (drop any claim not backed by
    a stored fact) — the same "ground the AI in real data" thesis, applied to copy.
  - design_json persistence sets up reopen-to-edit without paying for a new AI image.

═══════════════════════════════════════════════
SLICE 2 — SHIPPED (editable react-konva label/badge editor + two-stage UX)
═══════════════════════════════════════════════
Alembic head: b7e3f1a06c92 (unchanged — no new columns). Tests: 68 passing.
NEW DEP (frontend): npm i react-konva@19 konva  (React 19 → react-konva 19).

WHY: gpt-image-1 was cropping headlines and garbling text. Fix = stop asking the AI
for text at all. The AI now renders a background+product ONLY; every word (headline,
EXACT price, badges, store name) is a crisp, deterministic canvas label the owner can
move and edit. Text is never cropped and always spelled exactly.

BACKEND (already in place from the export/save work):
  - generate_ad_creative now composes the prompt with background_only=True, so the
    image has clean empty space (left half) for the overlay.
  - initial_design_json seeds the overlay with left-aligned labels (headline top-left,
    badges, big red price_tag, supporting blocks, store banner at the bottom edge).
  - POST /creative/{id}/export {image_base64, design_json?}: decodes the canvas PNG
    (strips the "data:image/png;base64," prefix), saves via storage_service →
    final_image_url, persists design_json. Store-scoped (404 on cross-store id).
  - PUT  /creative/{id}/design {design_json}: save-draft without re-exporting.

FRONTEND:
  - NEW src/pages/creative/LabelEditor.jsx (react-konva):
      <Stage> scaled to fit (460px display, exports at full canvas res via
      pixelRatio = canvasW / displayW). Background drawn as a Rect fillPatternImage
      (crossOrigin='anonymous' → Cloudinary export isn't canvas-tainted).
      Each label = <Group draggable> of an optional shape <Rect cornerRadius…> +
      <Text>. Selection attaches a <Transformer> (resize + rotate); transform bakes
      scale back into width/height so font stays crisp.
      Controls: badge PRESETS (New Arrival, Limited Edition, Staff Pick, Best Seller,
      Weekend Deal, While Supplies Last, 750 ML, In Stock), add free text, per-element
      text / font size / text colour / shape (none/rounded/pill/price_tag/ribbon/
      circle) / shape colour / font family / bold, reorder (forward/back), duplicate,
      delete, undo/redo (history stack), Save draft, Export ad.
      onExport(dataUrl, designJson) → creativeApi.exportFinal; onSave → saveDesign.
  - Creative.jsx is now TWO-STAGE: after Generate, a background-only creative
    (has design_json) drops straight into the editor. The result card shows the
    final_image_url once exported, with an "Edit labels" button to reopen the editor
    (rehydrated from the saved design_json — no AI regeneration, no new spend).
  - client.js: creativeApi.exportFinal(creativeId, imageBase64, designJson) already added.

TESTS: tests/test_design_overlay.py (7, pure): every label has editor geometry +
  unique ids; source_image/canvas preserved; portrait (1536) canvas honoured; saved
  design round-trips (move + add badge, exact price survives); price is a label not
  pixels; old creative (design_json=None) is simply not editable; export data-URL
  decode (prefixed + bare base64).  Full suite: 68 passed.

RUN / TEST / SHIP (slice 2):
  cd ~/Desktop/LiquorIQ/frontend && npm i react-konva@19 konva
  cd ~/Desktop/LiquorIQ/backend && source venv/bin/activate && pytest -q   # 68 passed
  # (no migration — Slice 1's b7e3f1a06c92 already added design_json)
  # AI Strategy → Create ad → Generate → editor opens → drag/edit labels → Export ad.
  git add -A && git commit -m "feat(creative): background-only images + react-konva label editor + two-stage Creative (Slice 2)"
  git push origin main

INTERVIEW NOTES (Slice 2):
  - "Don't fight the tool": generative image models are unreliable at exact text, so
    we removed text from the AI's job entirely and composited it deterministically —
    correctness by construction, not by prompt-tuning.
  - Canvas as source of truth: labels live in React state → serialize to design_json →
    export via stage.toDataURL(). Same JSON rehydrates the editor, so reopen-to-edit
    costs zero AI calls.
  - CORS + canvas taint: setting crossOrigin='anonymous' on the background image lets
    the Cloudinary-hosted asset be exported without tainting the canvas.

DO NOT begin Meta/Twilio in this feature. Reuse strategy, real-photo library,
Cloudinary, storage abstraction, AdCreative records, and design_plan/design_json.

POSSIBLE FOLLOW-UPS (not built): reusable saved presets (label_presets table),
subtext lines, more shapes (starburst/seal/chalkboard), icons, snapping/guides.
