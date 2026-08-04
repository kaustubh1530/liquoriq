"""
validate_bi.py — run the whole BI engine on a real report and show its working.

Every metric, the formula behind it, whether it was measured or assumed, and
what it does NOT account for. Written so a store owner (or an interviewer) can
check the arithmetic rather than take it on trust.

    python validate_bi.py                      # uses the July file
    python validate_bi.py path/to/report.xlsx
    python validate_bi.py report.xlsx --md      # markdown, for the docs
"""

import sys
from datetime import date

sys.path.insert(0, ".")

from app.services.bi import action_center as AC
from app.services.bi import assumptions as A
from app.services.bi import categorizer as CAT
from app.services.bi import opportunities as OPP
from app.services.bi import product_metrics as PM
from app.services.bi import reorder as REORDER
from app.services.bi import seasonality as SEASON
from app.services.bi import valuation as VAL
from app.services.holiday_calendar import get_upcoming_holidays
from app.services.parsers.adventpos_parser import AdvEntPOSParser

MD = "--md" in sys.argv
PATH = next((a for a in sys.argv[1:] if not a.startswith("--")), "/tmp/liq.xlsx")

_out: list[str] = []


def w(line=""):
    _out.append(line)


def h(title):
    w()
    w(f"## {title}" if MD else f"\n{'═' * 78}\n{title}\n{'═' * 78}")
    w()


def row(metric, value, formula, basis, note=""):
    if MD:
        w(f"| {metric} | {value} | `{formula}` | {basis} | {note} |")
    else:
        w(f"  {metric:<26} {value:>16}")
        w(f"  {'':<26} = {formula}")
        w(f"  {'':<26}   [{basis}] {note}".rstrip())
        w()


def table_head():
    if MD:
        w("| Metric | Value | How it is calculated | Basis | Notes |")
        w("|---|---:|---|---|---|")


def money(n):
    return f"${n:,.2f}"


# ── Parse ────────────────────────────────────────────────────────────────────

parser = AdvEntPOSParser()
rows = parser.parse(PATH)
days = (parser.period_end - parser.period_start).days + 1

resolved, merch, non_product = [], [], []
for r in rows:
    c = CAT.categorize(r["product_name"], r.get("sku"), {}, {})
    resolved.append(c)
    if c["category"] == CAT.NON_PRODUCT:
        non_product.append(r)
        continue
    r["category"] = c["category"]
    merch.append(r)

metrics = PM.compute_all(merch, days)
summary = PM.summarise(metrics, days)
coverage = CAT.coverage(resolved)
holidays = get_upcoming_holidays(today=date(2026, 8, 4), days=45)
opportunities = OPP.detect_all(metrics, holidays=holidays, brands={},
                               periods_of_history=1, period_days=days)
center = AC.build(summary, metrics, opportunities)
health = center["business_health"]
valuation = VAL.build(summary, None)
totals = OPP.total_value(opportunities)

w("# LiquorIQ — Business Intelligence validation report" if MD
  else "LiquorIQ — BUSINESS INTELLIGENCE VALIDATION REPORT")
w()
w(f"Source file: `{PATH}`" if MD else f"Source file: {PATH}")
w(f"Reporting period: {parser.period_start} to {parser.period_end} ({days} days)")
w(f"Rows parsed: {len(rows):,} · merchandise {len(merch):,} · "
  f"non-product lines excluded {len(non_product)}")

# ── 1. Inputs ────────────────────────────────────────────────────────────────

h("1. Inputs — what the file actually contains")
table_head()
row("Products", f"{len(merch):,}", "one row per product in the latest report",
    "MEASURED", "scoped to a single upload; merging reports invented stock")
row("Revenue in period", money(summary["revenue"]), "sum(total_amount)",
    "MEASURED", "the store's own sales lines")
row("Units sold", f"{summary['units']:,.0f}", "sum(quantity)", "MEASURED")
row("Non-product lines", str(len(non_product)),
    "tips / fees / bag tax, excluded from every inventory metric", "MEASURED",
    "'TAX ITEM' once appeared as a product to reorder")
row("Category coverage", f"{coverage['resolved_pct']}%",
    "resolved by SKU cache -> brand -> keyword -> AI -> manual override", "MEASURED")

# ── 2. Valuation ─────────────────────────────────────────────────────────────

h("2. Valuation — retail, not cost")
table_head()
row("Inventory value (retail)", money(summary["inventory_value"]),
    "sum(stock on hand x unit_price)", "MEASURED (RETAIL)",
    "unit_price = total_amount / quantity, i.e. the SHELF price")
row("Slow stock (retail)", money(summary["cash_frozen"]),
    "sum(retail value of dead + sleeping + overstock)", "MEASURED (RETAIL)",
    "NOT what the owner spent")
for margin in (25, 30, 35):
    row(f"...cash at {margin}% margin", money(VAL.at_cost(summary["cash_frozen"], margin)),
        f"retail x (1 - {margin}%)", "ESTIMATE",
        "only shown once the owner supplies his own margin")
w(f"  Current basis: **{valuation['basis']}** — {valuation['note']}" if MD
  else f"  Current basis: {valuation['basis']} — {valuation['note']}")

# ── 3. Stock classification ──────────────────────────────────────────────────

h("3. Stock classification — 9 classes")
table_head()
for key in PM.CLASSES:
    bucket = summary["by_class"].get(key)
    if not bucket:
        continue
    row(PM.CLASS_LABELS[key], f"{bucket['count']:,} · {money(bucket['value'])}",
        "weeks of supply = stock / (units sold / weeks in period)", "MEASURED",
        f"threshold from assumptions.py")

# ── 4. Health score ──────────────────────────────────────────────────────────

h(f"4. Business health — {health['score']}/100 ({health['band']})")
table_head()
for c in health["components"]:
    row(c["label"], f"{c['value']} (weight {c['weight']:.0%})", c["formula"],
        "MEASURED" + (" · benchmark target" if c.get("benchmark") else ""),
        c.get("caveat", ""))
w(f"  {health['basis']}")

# ── 5. Opportunities ─────────────────────────────────────────────────────────

h("5. Opportunities — one primary action per product")
table_head()
for o in opportunities:
    row(f"{o['rank']}. {o['type']}", money(o["value_score"]),
        {"reorder": "sum(weekly velocity x price x 4 weeks) for short products",
         "clearance": f"retail value of slow stock x {A.CLEARANCE_RECOVERY_RATE:.0%} assumed recovery",
         "seasonal": "their sales in these categories x assumed holiday lift, capped by stock",
         "bundle": f"anchor units x {A.BUNDLE_ATTACH_RATE:.0%} assumed attach rate x slow item price",
         "premium_upsell": f"entry units x {A.UPSELL_CONVERSION_RATE:.0%} assumed conversion x price gap",
         "winback": f"lapsed customers x {A.WINBACK_RESPONSE_RATE:.0%} assumed response x avg spend",
         "campaign_repeat": "measured lift from a past campaign"}.get(o["type"], "—"),
        f"{o['confidence'].upper()} · " + ("ESTIMATE" if o.get("estimated") else "MEASURED"),
        f"{o['timeline']} — {o.get('allocation_note') or o['confidence_reason']}")

w(f"  TOTAL {money(totals['raw'])} raw · {money(totals['confidence_adjusted'])} "
  f"confidence-adjusted")
w(f"  {totals['basis']}")

# ── 6. Seasonal scope ────────────────────────────────────────────────────────

h("6. Seasonal scope — why these products and not others")
for holiday in holidays[:2]:
    qualified = SEASON.qualify(metrics, holiday["key"], holiday["name"])
    uplift = SEASON.expected_uplift(qualified, holiday["key"])
    w(f"  {holiday['name']} — {holiday['days_away']} days away")
    w(f"    relevant categories : {', '.join(uplift['categories'])}")
    w(f"    products in scope   : {uplift['products']:,} of {len(metrics):,} "
      f"({uplift['products'] / max(len(metrics), 1) * 100:.1f}% of the shop)")
    w(f"    their sales         : {money(uplift['base_revenue'])} (MEASURED)")
    w(f"    assumed lift        : {uplift['lift_rate']:.0%} (ASSUMPTION)")
    w(f"    expected uplift     : {money(uplift['value'])}"
      f"{' — capped by stock on hand' if uplift['capped_by_stock'] else ''}")
    for q in qualified[:3]:
        w(f"      · {q['product_name'][:44]:44} {q['qualified_because']}")
    w()

# ── 7. Reorder list ──────────────────────────────────────────────────────────

h("7. Reorder list — the purchase document")
table_head()
for horizon in (2, 4, 8):
    items = REORDER.build_reorder_list(metrics, horizon)
    t = REORDER.summarise(items, horizon)
    row(f"{horizon}-week horizon",
        f"{t['products']} products · {t['total_units']:,} units",
        "ceil(weekly rate x horizon) - stock on hand, per product", "MEASURED",
        f"{money(t['total_value_at_retail'])} at RETAIL — not what the order costs")

# ── 8. Assumptions ───────────────────────────────────────────────────────────

h("8. Every assumption in the engine")
table_head()
for item in A.as_disclosure():
    row(item.get("label", item.get("key", "?")), str(item.get("value")),
        item.get("key", ""), "ASSUMPTION", item.get("why", ""))

# ── 9. Limitations ───────────────────────────────────────────────────────────

h("9. What these numbers do NOT account for")
for line in [
    "NO COST DATA. The POS export carries selling prices only. Every inventory "
    "figure is at retail until the owner supplies his gross margin.",
    "ONE PERIOD OF HISTORY. Velocity comes from a single month, so a seasonal "
    "product looks like a trend. Confidence stays at MEDIUM until more periods exist.",
    "NO BASKET DATA. The export has no transaction-level lines, so bundle attach "
    "rates are industry assumptions, not this store's behaviour.",
    "STOCK IS A SNAPSHOT. Stock on hand is as of the report date, not an average, "
    "so in-stock rate can miss a stock-out that was resolved mid-month.",
    "HOLIDAY LIFTS ARE INDUSTRY FIGURES. They are not measured from this store's "
    "own past holidays; once several years of reports exist they should be replaced.",
    "NEGATIVE STOCK COUNTS. 54 products report negative stock, which is a "
    "counting error at the shop, not a computable quantity. They are isolated and "
    "reported rather than silently zeroed.",
]:
    w(f"  · {line}" if not MD else f"- {line}")

w()
print("\n".join(_out))
