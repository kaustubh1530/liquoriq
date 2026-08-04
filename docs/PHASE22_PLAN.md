═══════════════════════════════════════════════
PHASE 22 — BUSINESS INTELLIGENCE ENGINE
Implementation plan (written BEFORE any code)
═══════════════════════════════════════════════

───────────────────────────────────────────────
PART A — WHAT THE REAL REPORT ACTUALLY CONTAINS
───────────────────────────────────────────────
Source: liqIQ.xlsx, run through the EXISTING parser (untouched).
1,403 products · period 01–31 Jul 2026.

  Revenue (month)          $66,753
  Units sold                 4,179
  Inventory value         $313,347   ← cash sitting on shelves
  Stock data present    1,403/1,403  (100%)

THE HEADLINE NUMBER — and the reason this phase exists:

  Weeks of supply          products      verdict
  ─────────────────────────────────────────────────────────
  < 2 weeks                     29       reorder now
  2–8 weeks                    257       healthy
  8–26 weeks                   468       heavy
  > 26 weeks                   466       OVERSTOCK  → $220,661
  sold out (0 stock)           116       lost sales
  negative stock                63       data quality flag
  zero sales                     4       truly dead

  · $220,661 of $313,347 (70%) is in products with MORE THAN SIX MONTHS
    of supply. That is the single biggest fact about this business.
  · Inventory turnover = $801k annualised ÷ $313k = 2.6× per year.
    Liquor retail benchmark is 4–6×. This store is roughly half as
    efficient as it should be, and the gap is ~$150k of trapped cash.
  · 116 products are SOLD OUT but were selling — ongoing lost revenue.
  · Revenue is Pareto: top 10% of products = 44% of revenue,
    top 20% = 60%. The tail is where the cash is stuck.

WHY THE CURRENT DASHBOARD MISSES ALL OF THIS
  analytics_service defines dead stock as `units_sold <= 0`. On this file
  that matches FOUR products. The existing Action Center therefore reports
  almost nothing while $220k rots. The definition, not the data, is the bug.
  Overstock is set at >16 weeks, which flags 466 products with no ranking —
  unusable as a to-do list. Velocity divides by a hard-coded 4.3 weeks
  regardless of the report's real period.

WHAT ELSE THE FILE WILL GIVE US (verified, not assumed)
  · Product SIZE is in the name for 96% of rows ("750 ml", "1.75 Lt",
    "12 Oz"). PACK format for 20% ("12-PACK CANS", "6-Pack").
    → enables size-ladder upsell and multipack bundle logic.
  · CATEGORY is NOT in the export (100% null) but is INFERABLE from the
    name. A quick keyword pass hit 52%; with a proper brand dictionary +
    varietal + format rules the target is 85%+.
    → this is what unlocks "category inventory value".
  · SKU/UPC present on 100% of rows → stable product identity across
    uploads, so period-over-period comparison is possible later.

WHAT THE FILE CANNOT GIVE US — stated honestly
  · NO COST → no true profit. All "value" figures are revenue or
    retail-value-of-inventory, never margin. We will label them as such and
    let the owner enter category margin assumptions.
  · NO PER-SALE DATES → one row per product per period. No day-of-week or
    intra-month trend from a single upload.
  · NO CUSTOMER LINK on POS rows → win-back opportunities come from the
    separately-uploaded customer list (RFM), not from this file.

───────────────────────────────────────────────
PART B — ARCHITECTURE
───────────────────────────────────────────────
Rule from the brief, and the spine of the design:
  **BUSINESS LOGIC IS DETERMINISTIC. GPT ONLY EXPLAINS.**
  Every number, threshold, ranking and recommendation is computed in pure
  Python and is unit-tested. GPT is handed the finished numbers and asked
  only to write the sentence a human reads. If OpenAI is down or out of
  credits, the entire engine still works — only the prose is missing.

NEW MODULES (all pure functions; no DB, no network → fully testable)

  services/bi/product_metrics.py
      One product in → one enriched record out. Weeks of supply, sell-
      through rate, turnover, days since last sale, stock status, health
      score 0-100, cash frozen. No I/O.

  services/bi/categorizer.py — CATEGORY INTELLIGENCE LAYER
      The POS export has NO category (100% null), so we resolve it through a
      5-tier cascade. First hit wins; every result carries its source and a
      confidence, and every result is CACHED BY SKU so the store gets faster
      and cheaper with each upload.

        TIER 1  MANUAL OVERRIDE     the owner's correction. Absolute
                                    authority, never overwritten by anything
                                    below. confidence = certain.
        TIER 2  SKU/UPC CACHE       already resolved for this SKU on a prior
                                    upload → reuse. SKU is on 100% of rows
                                    and is stable across periods, which makes
                                    it the right cache key (names get edited).
        TIER 3  BRAND DICTIONARY    "TITO'S" → Tito's → Vodka. Brand implies
                                    category with high confidence and also
                                    gives us the brand for upsell/bundling.
        TIER 4  CATEGORY DICTIONARY keyword, varietal ("CAB SAUV", "PINOT"),
                                    and container-format rules ("12-PACK
                                    CANS, 12 Oz" → beer/seltzer). Medium
                                    confidence.
        TIER 5  AI FALLBACK         only for names still unresolved. GPT is
                                    asked to pick from our FIXED category
                                    list — it classifies, it does not invent
                                    categories and it never touches a number.
                                    Batched, cached by SKU, low confidence,
                                    and skipped entirely when OpenAI is
                                    unavailable. Everything still works.
        else    "Uncategorised"     never a wild guess.

      NOTE ON RULE 4 OF THE BRIEF ("GPT never invents business logic"):
      classifying a bottle as Wine is DATA ENRICHMENT, not business logic.
      The financial maths never calls GPT. An AI-sourced category is marked
      as such in the UI so the owner can correct it, and a correction is
      promoted to Tier 1 forever.

      Also extracts, deterministically, from the name: SIZE (96% of rows),
      PACK format (20%), and BRAND — which is what makes premium-upsell and
      bundle detection possible.

      Persisted in a new `product_categories` table keyed on (store, sku).

  services/bi/opportunities.py
      Seven detectors, each returning a list of Opportunity records with a
      computed `value_score`. Pure ranking, no AI.

  services/bi/action_center.py
      Turns ranked opportunities into executive actions with the seven
      required fields, and assigns priority bands.

  services/bi/explain.py
      The ONLY place GPT is touched. Takes a finished action and returns a
      one-paragraph plain-English explanation. Falls back to a deterministic
      template string when the AI is unavailable.

  services/bi/assumptions.py
      Category margin assumptions + tunable thresholds in ONE place, so
      every number is traceable to a stated assumption.

CHANGED
  services/analytics_service.py   get_inventory_intelligence() rewritten to
                                  call the BI engine (keeps its endpoint).
  routes/analytics.py             + /analytics/opportunities, /actions
  frontend Dashboard.jsx          Action Center becomes the hero.

THE ONE NECESSARY PARSER TOUCH (flagged, ~4 lines, no logic change)
  The parser already regex-matches "From 01-Jul-2026 To 31-Jul-2026" but
  keeps only the END date. Velocity is currently divided by a hard-coded
  4.3 weeks, so a WEEKLY upload understates velocity 4× and every reorder /
  overstock verdict is wrong. Fix: assign `self.period_start` and
  `self.period_end` after parsing (assignment only — the parsing path is
  untouched), have parse_service persist period_start/period_end/period_days
  on `uploaded_reports`, and let the BI engine use the true period length.
  If you'd rather not touch the parser at all, the fallback is to ask the
  owner for the period on upload — worse UX, same result.

───────────────────────────────────────────────
PART C — THE METRICS (exact definitions)
───────────────────────────────────────────────
  weekly_velocity   = units_sold ÷ (period_days ÷ 7)
  weeks_of_supply   = stock_on_hand ÷ weekly_velocity      (∞ if no sales)
  sell_through_rate = units_sold ÷ (units_sold + stock_on_hand)
  turnover (annual) = (units_sold × periods_per_year) ÷ stock_on_hand
  cash_frozen       = stock_on_hand × unit_price   [retail value, not cost]
  days_of_supply    = weeks_of_supply × 7

  STOCK STATUS — 9 classes, first match wins.
  Measured on the real file (period = 31 days, TRUE length, not 4.3 weeks):

    class      products      cash      meaning / what to do
    ───────────────────────────────────────────────────────────────────
    negative         63        $0      stock < 0 — count is wrong, fix it
    sold_out        116        $0      stock 0 but selling — LOST SALES
    dead              4        $0      zero sales, has stock — never moved
    critical          7       $64      < 1 week — stock-out imminent
    reorder          56    $2,692      < 3 weeks — order this week
    healthy         371   $32,581      3–12 weeks — leave alone
    heavy           320   $57,350      12–26 weeks — watch
    overstock       264   $77,554      26–52 weeks — promote
    sleeping        202  $143,107      > 1 YEAR of supply — clearance
    ───────────────────────────────────────────────────────────────────
                   1,403  $313,347

  WHY SLEEPING IS SPLIT OUT FROM OVERSTOCK (the owner's addition, and it
  earns its place): lumping everything over 26 weeks together produced one
  undifferentiated pile of 466 products. Splitting at 52 weeks isolates
  $143,107 in 202 products that will not sell through within a YEAR. "Dead"
  in the old code caught 4 products; "sleeping" catches the real problem.
  Dead = never moved. Sleeping = moving, but so slowly the cash is gone.

  PRODUCT HEALTH SCORE (0-100) — "how well is this product doing?"
    40% supply balance  (peaks at 3–12 weeks, falls off both ways)
    30% sell-through
    20% revenue rank percentile within the store
    10% stock availability (penalise sold-out and negative)
    Bands: 80+ star · 60-79 healthy · 40-59 watch · <40 problem

  PRODUCT OPPORTUNITY SCORE (0-100) — "how much is there to GAIN here?"
    Deliberately NOT the inverse of health. A healthy product can carry a
    big opportunity (sold out and selling fast) and a sick one can carry a
    tiny one (dead $2 item nobody will ever buy). Ranks what to act on.
      50% money at stake     — cash frozen, or recoverable revenue, scaled
                               against the store's own largest position
      30% urgency            — from the stock class (sold_out/critical high,
                               heavy low)
      20% demand evidence    — units sold percentile; acting on a product
                               with real demand is likelier to pay off
    Bands: 70+ act now · 40-69 worth doing · <40 ignore for now
    Every product carries BOTH scores, so the UI can show "healthy but big
    opportunity" — which is exactly the sold-out best-seller case.

  BUSINESS HEALTH SCORE (0-100) — one number for the whole store
    35% inventory turnover vs the 4–6× benchmark
    25% share of inventory value sitting in healthy classes
    20% sell-through across the store
    10% availability (penalise the sold-out rate)
    10% data quality (penalise negative stock and unclassified products)
    Bands: 80+ strong · 60-79 stable · 40-59 needs attention · <40 at risk
    On the real file this lands in "needs attention": turnover 2.6× and 70%
    of cash in dead/overstock/sleeping. The score exists so the owner can
    watch ONE number move over time rather than reading nine tables.

───────────────────────────────────────────────
PART D — THE SEVEN OPPORTUNITY DETECTORS
───────────────────────────────────────────────
Each returns: type, title, evidence (the numbers), value_score (dollars),
confidence (high/med/low + why), products, suggested_action, deep link.

  1. REORDER          sold_out + critical items that were selling.
     value = weekly_velocity × price × 4  (a month of recoverable sales)
     confidence high when ≥2 periods of history, medium on a single upload.

  2. CLEARANCE        overstock and dead stock, ranked by cash frozen.
     value = cash_frozen × expected_recovery_rate (assumption: 60%).

  3. SEASONAL         upcoming holiday (existing holiday_calendar) matched
     against categories in stock. value = category stock value × uplift
     assumption. Only fires within the holiday's lead-time window.

  4. BUNDLE           products in the same category with healthy stock and
     complementary formats (e.g. spirit + mixer). value = attach-rate
     assumption × basket lift.

  5. PREMIUM UPSELL   same brand present in two sizes, or a premium tier in
     a category where the value tier sells well. value = price gap × units.

  6. WIN-BACK         from RFM: At Risk / Inactive segments.
     value = segment size × avg spend × recovery assumption.

  7. CAMPAIGN REPEAT  a past campaign with measured positive lift whose
     window has closed. value = the lift it actually produced.

  RANKING: every opportunity carries `value_score` in dollars plus a
  `confidence_weight` (high 1.0 / med 0.7 / low 0.4). Final sort key is
  value_score × confidence_weight, so a big shaky number cannot outrank a
  solid one. The formula is shown in the UI — no black box.

───────────────────────────────────────────────
PART E — EXECUTIVE ACTION CENTER (the 7 required fields)
───────────────────────────────────────────────
  priority          P1 critical / P2 high / P3 medium  (from value + urgency)
  business_impact   "$220,661 of cash frozen in 466 slow products"
  evidence          the raw numbers behind it, always visible
  expected_outcome  "Recover ~$132,000 at a 60% clearance rate"
  confidence        high/medium/low + the reason for the rating
  suggested_action  the concrete next step in plain words
  action            {label, route} → a real button (e.g. → /ai preloaded
                    with those products, or → /labels for shelf tags)

───────────────────────────────────────────────
PART F — IMPLEMENTATION ORDER  (APPROVED, in progress)
───────────────────────────────────────────────
  STATUS: steps 1–6 COMPLETE and green (278 tests passing).
          Steps 7–10 remain: routes, GPT explain, frontend, handoff.

  1. Parser: preserve period_start / period_end  ← APPROVED by owner  [DONE]
     + uploaded_reports columns + migration. Assignment only; the parsing
     path is untouched. Unlocks TRUE period length everywhere: velocity,
     weeks-of-supply, turnover, ROI windows, trend.
     Fallback when a file has no period line: assume 30 days AND mark the
     upload `period_estimated=true` so the UI can say so.
  2. assumptions.py — every threshold and margin in one traceable place
  3. categorizer.py — 5-tier cascade + product_categories table
  4. product_metrics.py — 9 classes, health score, opportunity score
  5. opportunities.py — 7 detectors, ranked by value × confidence
  6. action_center.py — 7 required fields + business health score
  7. Rewire analytics_service (keep the existing endpoint working) + routes
  8. explain.py — GPT prose only, deterministic fallback
  9. Frontend: Action Center hero, opportunity list, health score
 10. Verify against liqIQ.xlsx end-to-end, handoff doc

Every step ends green: `pytest -q` and `vite build`.
No step is allowed to make a financial number depend on GPT.

───────────────────────────────────────────────
PART G — STATED ASSUMPTIONS (all in assumptions.py, all editable)
───────────────────────────────────────────────
  Category gross margins (industry typical, owner-editable):
    spirits 30% · wine 33% · beer 22% · seltzer/RTD 25% · non-alc 40%
  Clearance recovery rate            60% of retail
  Holiday uplift                     15% of category stock value
  Win-back response rate             8% of contacted segment
  Reorder horizon                    4 weeks of recoverable sales
  Overstock threshold                26 weeks
  Reorder threshold                   3 weeks

  Every figure the engine reports is traceable to one of these, and each is
  labelled in the UI as an assumption rather than a fact.
