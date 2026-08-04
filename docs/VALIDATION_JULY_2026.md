# LiquorIQ — Business Intelligence validation report

Source file: `/tmp/liq.xlsx`
Reporting period: 2026-07-01 to 2026-07-31 (31 days)
Rows parsed: 1,403 · merchandise 1,393 · non-product lines excluded 10

## 1. Inputs — what the file actually contains

| Metric | Value | How it is calculated | Basis | Notes |
|---|---:|---|---|---|
| Products | 1,393 | `one row per product in the latest report` | MEASURED | scoped to a single upload; merging reports invented stock |
| Revenue in period | $65,351.19 | `sum(total_amount)` | MEASURED | the store's own sales lines |
| Units sold | 3,922 | `sum(quantity)` | MEASURED |  |
| Non-product lines | 10 | `tips / fees / bag tax, excluded from every inventory metric` | MEASURED | 'TAX ITEM' once appeared as a product to reorder |
| Category coverage | 99.2% | `resolved by SKU cache -> brand -> keyword -> AI -> manual override` | MEASURED |  |

## 2. Valuation — retail, not cost

| Metric | Value | How it is calculated | Basis | Notes |
|---|---:|---|---|---|
| Inventory value (retail) | $313,346.90 | `sum(stock on hand x unit_price)` | MEASURED (RETAIL) | unit_price = total_amount / quantity, i.e. the SHELF price |
| Slow stock (retail) | $220,660.61 | `sum(retail value of dead + sleeping + overstock)` | MEASURED (RETAIL) | NOT what the owner spent |
| ...cash at 25% margin | $165,495.46 | `retail x (1 - 25%)` | ESTIMATE | only shown once the owner supplies his own margin |
| ...cash at 30% margin | $154,462.43 | `retail x (1 - 30%)` | ESTIMATE | only shown once the owner supplies his own margin |
| ...cash at 35% margin | $143,429.40 | `retail x (1 - 35%)` | ESTIMATE | only shown once the owner supplies his own margin |
  Current basis: **retail** — Your POS export has no cost data. These are RETAIL values — what the stock would sell for, not what it cost you. Add your gross margin to see the cash actually tied up.

## 3. Stock classification — 9 classes

| Metric | Value | How it is calculated | Basis | Notes |
|---|---:|---|---|---|
| Negative stock — count is wrong | 54 · $0.00 | `weeks of supply = stock / (units sold / weeks in period)` | MEASURED | threshold from assumptions.py |
| Sold out — losing sales | 115 · $0.00 | `weeks of supply = stock / (units sold / weeks in period)` | MEASURED | threshold from assumptions.py |
| Dead — never moved | 4 · $0.00 | `weeks of supply = stock / (units sold / weeks in period)` | MEASURED | threshold from assumptions.py |
| Critical — under 1 week left | 7 · $63.52 | `weeks of supply = stock / (units sold / weeks in period)` | MEASURED | threshold from assumptions.py |
| Reorder — under 3 weeks left | 56 · $2,691.91 | `weeks of supply = stock / (units sold / weeks in period)` | MEASURED | threshold from assumptions.py |
| Healthy | 371 · $32,580.82 | `weeks of supply = stock / (units sold / weeks in period)` | MEASURED | threshold from assumptions.py |
| Heavy — 3 to 6 months | 320 · $57,350.04 | `weeks of supply = stock / (units sold / weeks in period)` | MEASURED | threshold from assumptions.py |
| Overstock — 6 to 12 months | 264 · $77,553.83 | `weeks of supply = stock / (units sold / weeks in period)` | MEASURED | threshold from assumptions.py |
| Sleeping — over a year of stock | 202 · $143,106.78 | `weeks of supply = stock / (units sold / weeks in period)` | MEASURED | threshold from assumptions.py |

## 4. Business health — 39.4/100 (at risk)

| Metric | Value | How it is calculated | Basis | Notes |
|---|---:|---|---|---|
| Inventory turnover | 2.46 (weight 35%) | `period revenue x (365 / period days) / retail inventory value` | MEASURED · benchmark target | Revenue and inventory are both at RETAIL, so the ratio is comparable year to year but is not a cost-based turnover. |
| Cash in healthy stock | 11.3 (weight 25%) | `retail value of healthy/reorder/critical stock / total retail value` | MEASURED · benchmark target |  |
| Sell-through rate | 17.6 (weight 20%) | `units sold / (units sold + units on hand)` | MEASURED |  |
| In-stock rate | 91.7 (weight 10%) | `1 - (products sold out / products)` | MEASURED · benchmark target | A snapshot as of the report date, not an average over the month. |
| Data quality | 95.3 (weight 10%) | `1 - ((negative stock counts + uncategorised) / products)` | MEASURED |  |
  Every component is measured from your own report. The WEIGHTS and the TARGETS are industry benchmarks, not your history — the score is a consistent yardstick, not a verdict.

## 5. Opportunities — one primary action per product

| Metric | Value | How it is calculated | Basis | Notes |
|---|---:|---|---|---|
| 1. clearance | $132,396.37 | `retail value of slow stock x 60% assumed recovery` | HIGH · ESTIMATE | This quarter — the frozen cash is measured from your own stock and sales; the 60% recovery rate is an assumption |
| 2. reorder | $9,994.86 | `sum(weekly velocity x price x 4 weeks) for short products` | MEDIUM · ESTIMATE | Today — based on a single reporting period — upload again to confirm the trend |
| 3. seasonal | $3,359.86 | `their sales in these categories x assumed holiday lift, capped by stock` | MEDIUM · ESTIMATE | Before Labor Day Weekend — 185 products moved to a higher-value action, so they are not counted twice. |
  TOTAL $145,751.09 raw · $141,744.67 confidence-adjusted
  Each product contributes to one opportunity only — its highest-value action — so these totals are not double-counted. Figures marked as estimates depend on assumed rates.

## 6. Seasonal scope — why these products and not others

  Labor Day Weekend — 28 days away
    relevant categories : Beer, Seltzer/RTD, Tequila
    products in scope   : 514 of 1,393 (36.9% of the shop)
    their sales         : $26,335.50 (MEASURED)
    assumed lift        : 20% (ASSUMPTION)
    expected uplift     : $5,267.10
      · TRULY REDWHITE SUMMER VARIETY , 12 Oz, 12-PA Seltzer/RTD is a core Labor Day Weekend category
      · 19 CRIMES CALI ROSE, 750 ml                  name matches “rose”, which sells for Labor Day Weekend
      · CH MONTAUD ROSE , 750 ml                     name matches “rose”, which sells for Labor Day Weekend


## 7. Reorder list — the purchase document

| Metric | Value | How it is calculated | Basis | Notes |
|---|---:|---|---|---|
| 2-week horizon | 144 products · 281 units | `ceil(weekly rate x horizon) - stock on hand, per product` | MEASURED | $4,118.45 at RETAIL — not what the order costs |
| 4-week horizon | 178 products · 599 units | `ceil(weekly rate x horizon) - stock on hand, per product` | MEASURED | $8,076.74 at RETAIL — not what the order costs |
| 8-week horizon | 178 products · 1,370 units | `ceil(weekly rate x horizon) - stock on hand, per product` | MEASURED | $18,635.73 at RETAIL — not what the order costs |

## 8. Every assumption in the engine

| Metric | Value | How it is calculated | Basis | Notes |
|---|---:|---|---|---|
| Clearance recovers | 60% of retail value | `clearance_recovery` | ASSUMPTION | A discounted bottle sells below shelf price. The frozen amount itself is measured; this rate is not. |
| A clearance can add | 15% to a normal month's sales | `clearance_capacity` | ASSUMPTION | Used to phase large clearances. A clearance competes with normal trade, so it cannot all happen at once. |
| Holiday lift | 8–35% of what the relevant products already sell, per holiday | `holiday_uplift` | ASSUMPTION | Applied ONLY to the categories that move for that holiday, and capped by stock on hand. Industry figures, not this store's own holiday history — replace once several years of reports exist. |
| Win-back response | 8% of those contacted | `winback_response` | ASSUMPTION | Typical direct-marketing response. The segment sizes and past spend behind it are real. |
| Bundle attach rate | 12% | `bundle_attach` | ASSUMPTION | The POS export has no basket-level data, so this cannot yet be measured from the store's own transactions. |
| Upsell conversion | 10% | `upsell_conversion` | ASSUMPTION | The price gaps are real; the share of customers who trade up is not. |
| Stock-out costs | 4 weeks of lost sales | `reorder_horizon` | ASSUMPTION | How far ahead a reorder is valued. Longer horizons produce bigger figures without more evidence. |
| Healthy turnover | 4–6x per year | `turnover_benchmark` | ASSUMPTION | An industry benchmark used as a target, not a measurement of this store. |
| Cost of goods | unknown unless the owner supplies a gross margin | `margins` | ASSUMPTION | The POS export carries selling prices only. Until a margin is entered, every inventory figure is at RETAIL and labelled so. |

## 9. What these numbers do NOT account for

- NO COST DATA. The POS export carries selling prices only. Every inventory figure is at retail until the owner supplies his gross margin.
- ONE PERIOD OF HISTORY. Velocity comes from a single month, so a seasonal product looks like a trend. Confidence stays at MEDIUM until more periods exist.
- NO BASKET DATA. The export has no transaction-level lines, so bundle attach rates are industry assumptions, not this store's behaviour.
- STOCK IS A SNAPSHOT. Stock on hand is as of the report date, not an average, so in-stock rate can miss a stock-out that was resolved mid-month.
- HOLIDAY LIFTS ARE INDUSTRY FIGURES. They are not measured from this store's own past holidays; once several years of reports exist they should be replaced.
- NEGATIVE STOCK COUNTS. 54 products report negative stock, which is a counting error at the shop, not a computable quantity. They are isolated and reported rather than silently zeroed.

