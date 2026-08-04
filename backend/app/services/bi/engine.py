"""
services/bi/engine.py — PHASE 22: orchestration

The only module in services/bi that touches the database. It gathers the
inputs, runs the pure engine, and returns one payload for the Executive
Dashboard.

Sequence:
    latest stock snapshot per product   (DISTINCT ON, store-scoped)
  + the TRUE reporting period            (from the most recent upload)
  + category resolution                  (5-tier cascade, cached by SKU)
  → product metrics (9 classes, 2 scores)
  → opportunities (7 detectors, ranked)
  → action center + business health

Everything above is deterministic. The GPT explanation is added afterwards, is
optional, and cannot change a single number.
"""

import logging
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.normalized_sale import NormalizedSale
from app.models.product_category import ProductCategory
from app.models.uploaded_report import ReportStatus, UploadedReport
from app.services.bi import action_center as AC
from app.services.bi import assumptions as A
from app.services.bi import categorizer as CAT
from app.services.bi import opportunities as OPP
from app.services.bi import product_metrics as PM
from app.services.bi import valuation as VAL

logger = logging.getLogger(__name__)


async def _latest_upload_id(store_id: uuid.UUID, db: AsyncSession) -> uuid.UUID | None:
    """
    The most recent upload that actually produced sales rows.

    Joined rather than taken from uploaded_reports alone, because a customer
    file or a failed parse leaves an upload row with no sales behind it — and
    scoping the dashboard to an empty upload would blank the whole thing.
    """
    stmt = (
        select(NormalizedSale.upload_id)
        .join(UploadedReport, UploadedReport.id == NormalizedSale.upload_id)
        .where(NormalizedSale.store_id == store_id)
        .order_by(UploadedReport.uploaded_at.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalars().first()


async def _latest_snapshot(store_id: uuid.UUID, db: AsyncSession,
                           upload_id: uuid.UUID | None = None) -> list[dict]:
    """
    The store's CURRENT position: one row per product, from the most recent
    upload only.

    SCOPING TO ONE UPLOAD IS THE WHOLE POINT. This previously selected every
    row the store had ever uploaded and de-duplicated by product name, which
    silently merged five different reporting periods into a single "snapshot".
    Products that appeared in an old report but not the current one survived
    with their old figures — stock 0, sales > 0 — which the engine correctly
    read as "sold out, losing sales" for products that were simply no longer
    stocked.

    On real data that turned 1,393 products into 2,415, and 115 genuine
    stock-outs into 1,065. The reorder opportunity read $846,785 against a
    store whose ENTIRE monthly revenue is $66,753 — an 85x overstatement on
    the headline number the owner is asked to act on.

    A stock level is only meaningful as of the report it came from. Mixing
    reports produces a position that never existed.
    """
    stmt = select(
        NormalizedSale.product_name,
        NormalizedSale.sku,
        NormalizedSale.category,
        NormalizedSale.quantity,
        NormalizedSale.unit_price,
        NormalizedSale.total_amount,
        NormalizedSale.stock_on_hand,
        NormalizedSale.sale_date,
    ).where(NormalizedSale.store_id == store_id)

    if upload_id is not None:
        stmt = stmt.where(NormalizedSale.upload_id == upload_id)

    # Still DISTINCT ON: a single report can reprint a product across page
    # boundaries, and the parser's de-duplication is not guaranteed upstream.
    stmt = stmt.distinct(NormalizedSale.product_name).order_by(
        NormalizedSale.product_name, NormalizedSale.sale_date.desc().nulls_last()
    )

    rows = (await db.execute(stmt)).all()
    return [
        {
            "product_name": r.product_name, "sku": r.sku, "category": r.category,
            "quantity": r.quantity, "unit_price": r.unit_price,
            "total_amount": r.total_amount, "stock_on_hand": r.stock_on_hand,
            "sale_date": r.sale_date,
        }
        for r in rows
    ]


async def _period_context(store_id: uuid.UUID, db: AsyncSession,
                          upload_id: uuid.UUID | None = None) -> dict:
    """
    The TRUE reporting period, and how many periods of history we hold — which
    is what separates a "medium" confidence claim from a "high" one.

    The period MUST come from the same upload the snapshot came from. Taking it
    from "the latest completed upload" instead would divide one report's units
    by another report's day count whenever the newest upload produced no sales
    rows — a quiet, plausible-looking error in every velocity figure.
    """
    stmt = (
        select(UploadedReport)
        .where(UploadedReport.store_id == store_id,
               UploadedReport.status == ReportStatus.COMPLETED)
        .order_by(UploadedReport.uploaded_at.desc())
    )
    uploads = list((await db.execute(stmt)).scalars().all())
    if not uploads:
        return {"period_days": A.DEFAULT_PERIOD_DAYS, "estimated": True,
                "periods": 0, "uploads": 0,
                "period_start": None, "period_end": None}

    latest = next((u for u in uploads if u.id == upload_id), uploads[0])

    # DISTINCT PERIODS, not upload count. "periods" decides whether a velocity
    # claim is high or medium confidence, and the same month uploaded six times
    # is one month of evidence, not six. Counting uploads let a single report
    # claim "velocity confirmed across several uploads".
    distinct_periods = {
        (u.period_start, u.period_end) for u in uploads
        if u.period_start and u.period_end
    }
    periods = len(distinct_periods) or len(uploads)

    return {
        "period_days": latest.period_days or A.DEFAULT_PERIOD_DAYS,
        "estimated": bool(latest.period_estimated or not latest.period_days),
        "periods": periods,
        "uploads": len(uploads),
        "period_start": latest.period_start,
        "period_end": latest.period_end,
    }


async def _store_margin(store_id: uuid.UUID, db: AsyncSession) -> int | None:
    """The owner's gross margin, or None. Never defaulted — see valuation.py."""
    from app.models.store import Store
    return (await db.execute(
        select(Store.gross_margin_pct).where(Store.id == store_id)
    )).scalars().first()


async def _category_maps(store_id: uuid.UUID, db: AsyncSession) -> tuple[dict, dict]:
    """
    Tiers 1 and 2 of the cascade, loaded from the database:
    manual overrides (the owner's corrections) and the SKU cache.
    """
    rows = (await db.execute(
        select(ProductCategory).where(ProductCategory.store_id == store_id)
    )).scalars().all()

    overrides, cache = {}, {}
    for row in rows:
        entry = {"category": row.category, "brand": row.brand}
        (overrides if row.source == "manual" else cache)[row.product_key] = entry
    return overrides, cache


async def _persist_new_categories(
    store_id: uuid.UUID, resolved: list[tuple[str, dict]], db: AsyncSession
) -> int:
    """
    Cache anything newly resolved by the dictionaries, keyed by SKU. Next upload
    skips straight to tier 2 — the store gets faster and cheaper over time.
    """
    existing = {
        r.product_key for r in (await db.execute(
            select(ProductCategory).where(ProductCategory.store_id == store_id)
        )).scalars().all()
    }
    added = 0
    for key, result in resolved:
        if key in existing or result["source"] in ("manual", "cache", "fallback"):
            continue
        db.add(ProductCategory(
            store_id=store_id, product_key=key,
            product_name=result.get("product_name", "")[:500],
            category=result["category"], brand=result.get("brand"),
            source=result["source"], confidence=result["confidence"],
        ))
        existing.add(key)
        added += 1
    if added:
        await db.commit()
    return added


async def build_intelligence(
    store_id: uuid.UUID,
    db: AsyncSession,
    today: date | None = None,
    persist_categories: bool = True,
) -> dict:
    """
    The whole Business Intelligence payload. Pure engine, DB inputs only.
    Never calls GPT — explanations are layered on by the route if asked for.
    """
    # Resolve the source report ONCE, so the stock levels, the sales figures
    # and the period length all describe the same report. Deriving them
    # independently is how a snapshot that never existed gets assembled.
    upload_id = await _latest_upload_id(store_id, db)
    products = await _latest_snapshot(store_id, db, upload_id)
    period = await _period_context(store_id, db, upload_id)

    if not products:
        return _empty(period)

    # ── Category Intelligence Layer ──
    overrides, cache = await _category_maps(store_id, db)
    resolved, to_persist, brands = [], [], {}
    merchandise = []

    for product in products:
        result = CAT.categorize(product["product_name"], product.get("sku"),
                                overrides, cache)
        key = (product.get("sku") or "").strip() or product["product_name"].upper()
        resolved.append(result)
        to_persist.append((key, {**result, "product_name": product["product_name"]}))

        # Fees, tips and bag tax are not merchandise and must not pollute
        # inventory metrics — "TAX ITEM" was previously reported as a product
        # to reorder.
        if result["category"] == CAT.NON_PRODUCT:
            continue
        product["category"] = result["category"]
        if result.get("brand"):
            brands[product["product_name"]] = result["brand"]
        merchandise.append(product)

    if persist_categories:
        try:
            await _persist_new_categories(store_id, to_persist, db)
        except Exception:  # noqa: BLE001 — caching is an optimisation, never fatal
            logger.warning("Could not cache resolved categories", exc_info=True)
            await db.rollback()

    # ── Deterministic engine ──
    metrics = PM.compute_all(merchandise, period["period_days"])
    summary = PM.summarise(metrics, period["period_days"])

    holidays = _holidays(today)
    segments = await _segments(store_id, db)
    campaigns = await _campaigns(store_id, db)

    opportunities = OPP.detect_all(
        metrics, holidays=holidays, segments=segments, campaigns=campaigns,
        brands=brands, periods_of_history=period["periods"],
        period_days=period["period_days"],
    )
    center = AC.build(summary, metrics, opportunities)

    return {
        **center,
        "summary": summary,
        # Retail vs cost, decided in ONE place. Without the owner's margin this
        # reports retail and says so, rather than passing a shelf-price total
        # off as the cash he has tied up.
        "valuation": VAL.build(summary, await _store_margin(store_id, db)),
        "opportunities": opportunities,
        "categories": _category_intelligence(metrics),
        "coverage": CAT.coverage(resolved),
        "period": {
            "days": period["period_days"],
            "estimated": period["estimated"],
            "start": period["period_start"],
            "end": period["period_end"],
            "uploads": period.get("uploads", period["periods"]),
            "periods": period["periods"],
        },
        "products": sorted(metrics, key=lambda m: -m["opportunity_score"]),
        "non_product_lines": len(products) - len(merchandise),
    }


def _category_intelligence(metrics: list[dict]) -> list[dict]:
    """
    Per-category rollup, sorted by cash frozen — the owner's real question is
    "which part of my shop is holding my money?", not "which sold most".
    """
    buckets: dict[str, dict] = {}
    for m in metrics:
        key = m.get("category") or "Other"
        entry = buckets.setdefault(key, {
            "category": key, "products": 0, "revenue": 0.0, "units": 0.0,
            "inventory_value": 0.0, "cash_frozen": 0.0,
            "fast_movers": 0, "slow_movers": 0, "dead": 0, "sold_out": 0,
            "opportunity_score": 0.0,
        })
        entry["products"] += 1
        entry["revenue"] += m["revenue"]
        entry["units"] += m["units_sold"]
        entry["inventory_value"] += m["inventory_value"]
        entry["cash_frozen"] += m["cash_frozen"]
        entry["opportunity_score"] += m["opportunity_score"]
        if m["stock_class"] in ("healthy", "critical", "reorder"):
            entry["fast_movers"] += 1
        if m["stock_class"] in ("heavy", "overstock", "sleeping"):
            entry["slow_movers"] += 1
        if m["stock_class"] == "dead":
            entry["dead"] += 1
        if m["stock_class"] == "sold_out":
            entry["sold_out"] += 1

    out = []
    for entry in buckets.values():
        count = entry["products"] or 1
        entry["revenue"] = round(entry["revenue"], 2)
        entry["inventory_value"] = round(entry["inventory_value"], 2)
        entry["cash_frozen"] = round(entry["cash_frozen"], 2)
        entry["units"] = round(entry["units"], 1)
        entry["opportunity_score"] = round(entry["opportunity_score"] / count, 1)
        entry["frozen_pct"] = (round(entry["cash_frozen"] / entry["inventory_value"] * 100, 1)
                               if entry["inventory_value"] else 0.0)
        entry["turnover_share"] = 0.0
        out.append(entry)
    return sorted(out, key=lambda c: -c["cash_frozen"])


def _holidays(today: date | None):
    from app.services.holiday_calendar import get_upcoming_holidays
    try:
        return get_upcoming_holidays(today=today, days=45)
    except Exception:  # noqa: BLE001
        logger.warning("Holiday calendar unavailable", exc_info=True)
        return []


async def _segments(store_id: uuid.UUID, db: AsyncSession) -> dict:
    """
    RFM segments, reshaped for the win-back detector.

    Two things this has to get right, both learned the hard way:

    1. SHAPE. rfm.summarize() returns a LIST of
       {segment, count, total_spent, recommendation} — not a mapping — and it
       reports TOTAL spend, not average. The detector needs
       {name: {count, avg_spend}}, so the average is derived here. Reading it
       as a mapping raised AttributeError and took the whole dashboard down
       with a 500.

    2. CONTAINMENT. Customers are an optional feature — plenty of stores never
       upload a customer file. The reshaping therefore sits INSIDE the try,
       not after it. Previously the call was guarded but the parsing was not,
       so the guard protected nothing and the win-back opportunity's absence
       became a hard failure of the entire Business Control Center.

    Both list and mapping shapes are accepted, so a future change to
    summarize() degrades to "no win-back opportunity" rather than an outage.
    """
    try:
        from app.services.customer_service import segment_summary
        data = await segment_summary(store_id, db)

        raw = (data or {}).get("segments") or []
        if isinstance(raw, dict):
            pairs = list(raw.items())
        else:
            pairs = [(row.get("segment") or row.get("name"), row)
                     for row in raw if isinstance(row, dict)]

        out = {}
        for name, stats in pairs:
            if not name or not isinstance(stats, dict):
                continue
            count = int(stats.get("count") or stats.get("customers") or 0)
            if count <= 0:
                continue
            total = float(stats.get("total_spent") or stats.get("total_value") or 0.0)
            average = stats.get("avg_spend", stats.get("average_spend"))
            avg_spend = float(average) if average is not None else (total / count)
            out[name] = {
                "count": count,
                "avg_spend": round(avg_spend, 2),
                "total_spent": round(total, 2),
            }
        return out
    except Exception:  # noqa: BLE001 — customers are optional, never fatal
        logger.warning("Segment summary unavailable", exc_info=True)
        return {}


async def _campaigns(store_id: uuid.UUID, db: AsyncSession) -> list[dict]:
    """Past campaigns with a MEASURED lift — the strongest evidence we have."""
    try:
        from app.models.ai_strategy_report import AIStrategyReport
        from app.services.campaign_service import get_campaign_performance
    except Exception:  # noqa: BLE001
        return []

    try:
        strategies = list((await db.execute(
            select(AIStrategyReport)
            .where(AIStrategyReport.store_id == store_id)
            .order_by(AIStrategyReport.created_at.desc())
            .limit(5)
        )).scalars().all())
    except Exception:  # noqa: BLE001
        return []

    out = []
    for strategy in strategies:
        try:
            perf = await get_campaign_performance(strategy.id, store_id, db)
        except Exception:  # noqa: BLE001
            continue
        # The TOP-LEVEL key is total_revenue_lift. "revenue_lift" exists too,
        # but only inside each per-product row — reading it here always
        # returned None, so this detector silently never fired. A wrong key on
        # a .get() fails quietly, which is why it survived until now.
        perf = perf or {}
        lift = perf.get("total_revenue_lift")
        if lift is None:
            lift = perf.get("revenue_lift")
        if lift is None:
            continue
        created = strategy.created_at
        days_since = (date.today() - created.date()).days if created else 0
        out.append({
            "title": strategy.strategy_title,
            "strategy_id": str(strategy.id),
            "lift_revenue": lift,
            "days_since": days_since,
        })
    return out


def _empty(period: dict) -> dict:
    """No data yet — a real shape, so the dashboard renders an honest empty state."""
    summary = PM.summarise([], period["period_days"])
    return {
        **AC.build(summary, [], []),
        "summary": summary,
        "valuation": VAL.build(summary, None),
        "opportunities": [],
        "categories": [],
        "coverage": {"total": 0, "resolved": 0, "resolved_pct": 0.0,
                     "by_source": {}, "needs_ai": 0},
        "period": {"days": period["period_days"], "estimated": True,
                   "start": None, "end": None, "uploads": period["periods"]},
        "products": [],
        "non_product_lines": 0,
        "empty": True,
    }
