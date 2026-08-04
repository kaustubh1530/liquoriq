═══════════════════════════════════════════════
HOW LIQUORIQ WORKS — system overview
═══════════════════════════════════════════════
Written 2026-08-03 by reading the code, not the roadmap. Doubles as interview
prep: this is the "walk me through your system" answer.

───────────────────────────────────────────────
1. WHAT THE PRODUCT ACTUALLY IS
───────────────────────────────────────────────
LiquorIQ turns a liquor store's own POS export into marketing that is grounded
in that store's real numbers, then measures whether it worked.

The one-line pitch: **ChatGPT can write you an ad; it cannot tell you WHICH
bottle to promote, at what price, to whom, or whether it sold.** LiquorIQ can,
because it has the store's sales history.

The moat is not the AI creative (that's a commodity). It's the CLOSED LOOP:

    POS export → normalised sales → analytics → AI strategy → ad + labels
        → campaign to real customers → measured lift → back into the data

Every arrow in that chain is built. That is the whole product.

───────────────────────────────────────────────
2. UPLOAD → PARSE → NORMALISE
───────────────────────────────────────────────
STEP 1 — Upload (routes/uploads.py)
  The owner picks a file and a SOURCE (pos / website / uber_eats / doordash /
  other). The file is saved and an `uploaded_reports` row is created with
  status=pending. Nothing is parsed yet — upload and parse are separate so a
  bad file never leaves half-written data behind.

STEP 2 — Parse (services/parse_service.py + services/parsers/)
  A registry maps the source to a parser:
      POS       → AdvEntPOSParser   (the real pilot store's format)
      everything else → GenericParser
  parse_upload() sets status=processing, runs the parser, bulk-inserts the rows,
  then sets completed + rows_processed — or failed + error_message. The whole
  thing is wrapped so a parser blowing up marks the upload failed rather than
  500-ing the request.

  THE REAL FILE IS UGLY, and the parser is the least glamorous but most valuable
  code in the repo. The pilot store's "Sales By Item Summary Report" (.xls) is a
  PRINT-STYLE report, not a table:
      · 6 rows of store letterhead before any data
      · the header row REPEATS on every printed page (41 times in the real file)
      · page footers with timestamps and "Page N of M" interleaved
      · long product names WRAP onto continuation rows and must be re-joined
      · no unit price column → derived as sales ÷ quantity
      · no per-sale dates → it's a SUMMARY over a period
  Detection is layout-based (find a header containing both "UPC" and "Quantity
  Sold"), not by file extension.

STEP 3 — Normalise (models/normalized_sale.py)
  Every source collapses into ONE table, `normalized_sales`:
      product_name · sku · category · quantity · unit_price · total_amount
      stock_on_hand · sale_date · channel · customer_* · raw_row (audit trail)
  This is the key architectural decision: analytics, AI and campaigns are all
  written against this one shape, so adding DoorDash later is a new parser and
  nothing else. raw_row keeps the original cells so a bad parse is debuggable.

───────────────────────────────────────────────
3. WHAT THE DASHBOARD SHOWS (services/analytics_service.py)
───────────────────────────────────────────────
All six endpoints are plain SQL aggregates over `normalized_sales`, scoped to
the store. No AI involved.

  get_summary()              revenue, "orders", units, AOV, top channel,
                             date range, distinct products
  get_top_products()         best sellers by revenue
  get_slow_products()        worst movers
  get_category_performance() revenue split by category (pie)
  get_channel_performance()  POS vs delivery vs web
  get_sales_trend()          revenue over time (area chart)
  get_inventory_intelligence()  ← the interesting one

INVENTORY INTELLIGENCE is where raw data becomes money and instructions. It
takes the LATEST stock snapshot per product (Postgres DISTINCT ON), estimates
weekly velocity as units ÷ 4.3, and classifies every product:
      units sold = 0                → DEAD STOCK   (cash frozen on a shelf)
      < 2 weeks of stock left       → REORDER SOON
      > 16 weeks of stock           → OVERSTOCKED
It returns total inventory value, the worst offenders by dollar value, and a
ranked ACTION LIST ("$4,200 frozen in 12 dead products — generate a clearance
campaign") with links straight into the AI Strategy page.

That's the difference between a report and a product: the dashboard doesn't just
show numbers, it names the next action and links to the thing that does it.

───────────────────────────────────────────────
4. WHAT HAPPENS AFTER THAT
───────────────────────────────────────────────
AI STRATEGY (services/strategy_service.py)
  Assembles top sellers + categories + supplier DEAL BUYS + the US liquor
  HOLIDAY CALENDAR + (optionally) a customer segment, and asks GPT-4o for an
  occasion-led campaign: what to promote, why, to whom, the offer, and separate
  offline / online / Vivino plans. Deal buys carry cost and normal price so the
  model can reason about margin. Owner feedback killed the original
  "promote the slowest item" idea — the winning signal is occasion + deal.

AI AD CREATOR — gpt-image-1 paints the scene; Pillow typesets the headline,
  exact price and store name so nothing is ever misspelled or cropped.

LABEL STUDIO — printable shelf tags, prefilled from the store's own products
  and prices, 2–12 per A4 sheet.

CUSTOMERS + RFM (services/rfm.py) — uploaded customer lists are scored on
  recency / frequency / monetary and bucketed (VIP, At Risk, Inactive, Loyal…),
  which is what "target a segment" means upstream.

CAMPAIGNS — SMS (Twilio) and email to opted-in customers only, with suppression
  lists and an unsubscribe line. Nothing ever auto-sends.

ROI — campaign lift is derived LIVE from normalized_sales: a 14-day campaign
  window against a 28-day pre-campaign baseline. No snapshot table, so it's
  retroactive and self-correcting.

WEEKLY EMAIL — APScheduler sends every store a Monday 8am summary with a short
  GPT-written narrative.

───────────────────────────────────────────────
5. HONEST ASSESSMENT — WHERE IT'S WEAK
───────────────────────────────────────────────
Found by reading the code against the real file format.

A. "ORDERS" AND "AVERAGE ORDER VALUE" ARE WRONG. ★ most important
   get_summary() computes total_orders = COUNT(normalized_sales rows). But the
   real POS export is a per-PRODUCT summary, so one row = one product for the
   period, NOT one transaction. So the dashboard's "Orders" is really "product
   lines in the report", and AOV (revenue ÷ rows) is revenue per product line —
   a number that means nothing. A store owner reading "Average order value:
   $23.40" is being told something false. Either relabel to "Products sold /
   Avg revenue per product", or detect transaction-level files and only show
   true AOV then.

B. THE TREND CHART IS NEARLY FLAT BY CONSTRUCTION.
   The summary export has no per-sale dates, so the parser stamps EVERY row with
   the period end date. One upload = one point on the trend chart. Monthly
   uploads make the chart useless and make the 14-day ROI window meaningless.
   The parser docstring already says "weekly exports recommended" — but nothing
   in the UI tells the owner that, and nothing warns when a single upload spans
   31 days.

C. NO PROFIT ANYWHERE. Everything is revenue. A liquor store lives on margin,
   and margins vary hugely by category (spirits vs beer). Cost price exists only
   on DealBuy. Without cost, "top product by revenue" can be the wrong bottle to
   push. This is the single biggest missing dimension.

D. RE-UPLOADING THE SAME PERIOD DOUBLE-COUNTS. parse_upload() refuses to
   re-parse the same upload, but nothing stops uploading July twice as two
   files. Revenue silently doubles. There's no dedupe on (store, product,
   period) and no "this period overlaps an existing upload" warning.

E. THE DASHBOARD DOESN'T KNOW ABOUT TIME. Every figure is all-time. There's no
   "this month vs last month", no period picker. An owner's actual question is
   "am I up or down on last month?" and the dashboard cannot answer it.

F. VELOCITY IS A ROUGH GUESS. weekly = units ÷ 4.3 assumes every upload covers
   ~a month. If they upload weekly, velocity is understated 4×, so "reorder
   soon" and "dead stock" both misfire. It should use the report's actual period
   length, which the parser already extracts from the letterhead.

G. NOTHING CONNECTS INVENTORY TO THE CALENDAR. Dead stock is flagged, but the
   holiday calendar isn't consulted — "you have $900 of rosé and it's 3 weeks to
   Memorial Day" is the insight an owner would pay for.

───────────────────────────────────────────────
6. SUGGESTED ORDER OF WORK
───────────────────────────────────────────────
  1. Fix A (mislabelled orders/AOV) — small, and it stops the product lying.
  2. Fix F + B (use the real period length; warn on stale/long uploads) —
     makes reorder, dead stock and ROI trustworthy.
  3. Add D (overlap detection) — protects the numbers from the owner's own
     habits.
  4. Add E (period comparison) — turns the dashboard into something worth
     opening weekly.
  5. Add C (cost/margin import) — the biggest feature, and the one that makes
     every recommendation smarter.
  6. Then G (inventory × calendar) — the "wow" insight, best built on top of 5.
