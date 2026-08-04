"""
diagnose_bi.py — one-shot diagnosis of the /intelligence 500.

Runs the Business Intelligence engine against your REAL database, one stage at
a time, so the failing stage names itself instead of hiding behind a generic
500. Read-only: persist_categories is off, and nothing is committed.

    cd ~/Desktop/LiquorIQ/backend
    source venv/bin/activate
    python diagnose_bi.py
"""

import asyncio
import logging
import traceback

logging.disable(logging.INFO)  # mute SQLAlchemy echo — we want the error, not the SQL

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.store import Store


def stage(name):
    """Run one stage, print OK or the full traceback, and keep going."""
    def run(fn):
        try:
            result = fn()
            print(f"  OK   {name}")
            return result
        except Exception:
            print(f"\n  FAIL {name}\n" + "-" * 70)
            traceback.print_exc()
            print("-" * 70)
            raise SystemExit(1)
    return run


async def main():
    async with AsyncSessionLocal() as db:
        # Pick the store with the MOST sales rows, not simply the first one.
        # The first run diagnosed a store holding 5 rows while the browser was
        # logged into a different one — a diagnostic that inspects the wrong
        # subject can only mislead.
        from sqlalchemy import func

        from app.models.normalized_sale import NormalizedSale

        counts = dict((await db.execute(
            select(NormalizedSale.store_id, func.count())
            .group_by(NormalizedSale.store_id)
        )).all())

        stores = (await db.execute(select(Store))).scalars().all()
        if not stores:
            print("No stores found — nothing to diagnose.")
            return

        print("Stores in this database:")
        for s in stores:
            print(f"  {counts.get(s.id, 0):>6} sales rows   {s.name}  ({s.id})")

        store = max(stores, key=lambda s: counts.get(s.id, 0))
        print(f"\nDiagnosing: {store.name}  ({store.id})\n")

        from app.services.bi import action_center as AC
        from app.services.bi import categorizer as CAT
        from app.services.bi import engine as ENG
        from app.services.bi import opportunities as OPP
        from app.services.bi import product_metrics as PM

        products = await _try("1. latest stock snapshot", ENG._latest_snapshot(store.id, db))
        print(f"       → {len(products)} product rows")

        period = await _try("2. reporting period", ENG._period_context(store.id, db))
        print(f"       → {period}")

        overrides, cache = await _try("3. category maps", ENG._category_maps(store.id, db))
        print(f"       → {len(overrides)} overrides, {len(cache)} cached")

        merchandise, resolved, brands = [], [], {}
        try:
            for p in products:
                r = CAT.categorize(p["product_name"], p.get("sku"), overrides, cache)
                resolved.append(r)
                if r["category"] == CAT.NON_PRODUCT:
                    continue
                p["category"] = r["category"]
                if r.get("brand"):
                    brands[p["product_name"]] = r["brand"]
                merchandise.append(p)
            print(f"  OK   4. categorisation → {len(merchandise)} merchandise "
                  f"({len(products) - len(merchandise)} non-product)")
        except Exception:
            _fail("4. categorisation")

        try:
            metrics = PM.compute_all(merchandise, period["period_days"])
            summary = PM.summarise(metrics, period["period_days"])
            print(f"  OK   5. product metrics → {len(metrics)} products, "
                  f"${summary['inventory_value']:,.0f} inventory")
        except Exception:
            _fail("5. product metrics")

        holidays = await _try("6. holidays", _wrap(lambda: ENG._holidays(None)))
        segments = await _try("7. segments", ENG._segments(store.id, db))
        campaigns = await _try("8. campaigns", ENG._campaigns(store.id, db))
        print(f"       → {len(holidays)} holidays, {len(segments)} segments, "
              f"{len(campaigns)} campaigns")

        try:
            opps = OPP.detect_all(metrics, holidays=holidays, segments=segments,
                                  campaigns=campaigns, brands=brands,
                                  periods_of_history=period["periods"])
            print(f"  OK   9. opportunities → {len(opps)}")
        except Exception:
            _fail("9. opportunities")

        try:
            center = AC.build(summary, metrics, opps)
            print(f"  OK  10. action center → {len(center['actions'])} actions")
        except Exception:
            _fail("10. action center")

        payload = await _try("11. full build_intelligence",
                             ENG.build_intelligence(store.id, db, persist_categories=False))

        try:
            import json

            from fastapi.encoders import jsonable_encoder
            json.dumps(jsonable_encoder(payload))
            print("  OK  12. JSON serialisation")
        except Exception:
            _fail("12. JSON serialisation")

        print(f"\nEverything passed. Health {payload['business_health']['score']}/100, "
              f"{len(payload['actions'])} actions, {len(payload['products'])} products.")
        print("If the dashboard still 500s, the fault is in the route/auth layer,")
        print("not the engine.")


async def _try(name, awaitable):
    try:
        result = await awaitable
        print(f"  OK   {name}")
        return result
    except Exception:
        _fail(name)


def _wrap(fn):
    async def inner():
        return fn()
    return inner()


def _fail(name):
    print(f"\n  FAIL {name}\n" + "-" * 70)
    traceback.print_exc()
    print("-" * 70)
    raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
