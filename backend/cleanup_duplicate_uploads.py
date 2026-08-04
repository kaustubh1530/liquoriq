"""
cleanup_duplicate_uploads.py — remove sales rows from superseded reports.

parse_service now supersedes an earlier report covering the same period, but
that only applies to FUTURE uploads. This clears the duplicates already loaded.

A monthly summary is a statement about one period, not a batch of new sales.
Six uploads of July meant July's revenue was counted six times in every
store-wide total — which is why the revenue trend peaked at $220k for a store
whose July revenue was $66,753.

For each (store, period_start, period_end) it keeps the MOST RECENT completed
upload and deletes the sales rows belonging to the older ones. The
UploadedReport rows and the files on disk are left alone, so nothing is lost
and the upload history stays honest.

    cd ~/Desktop/LiquorIQ/backend
    source venv/bin/activate
    python cleanup_duplicate_uploads.py           # dry run — shows the plan
    python cleanup_duplicate_uploads.py --apply   # actually delete
"""

import asyncio
import logging
import sys

logging.disable(logging.INFO)

from sqlalchemy import delete, func, select

from app.database import AsyncSessionLocal
from app.models.normalized_sale import NormalizedSale
from app.models.store import Store
from app.models.uploaded_report import ReportStatus, UploadedReport


async def main(apply: bool) -> None:
    async with AsyncSessionLocal() as db:
        stores = {s.id: s.name for s in (await db.execute(select(Store))).scalars().all()}

        uploads = list((await db.execute(
            select(UploadedReport)
            .where(UploadedReport.status == ReportStatus.COMPLETED)
            .order_by(UploadedReport.uploaded_at.desc())
        )).scalars().all())

        counts = dict((await db.execute(
            select(NormalizedSale.upload_id, func.count())
            .group_by(NormalizedSale.upload_id)
        )).all())

        groups: dict[tuple, list] = {}
        for u in uploads:
            groups.setdefault((u.store_id, u.period_start, u.period_end), []).append(u)

        doomed, total_rows = [], 0
        for (store_id, start, end), members in sorted(
                groups.items(), key=lambda kv: str(kv[0])):
            if len(members) < 2:
                continue
            keep, drop = members[0], members[1:]
            drop = [u for u in drop if counts.get(u.id)]
            if not drop:
                continue

            window = f"{start} → {end}" if start else "unknown period"
            print(f"\n{stores.get(store_id, store_id)}  ·  {window}")
            print(f"  KEEP   {keep.original_filename}  "
                  f"({counts.get(keep.id, 0):,} rows, {keep.uploaded_at:%Y-%m-%d %H:%M})")
            for u in drop:
                rows = counts.get(u.id, 0)
                total_rows += rows
                doomed.append(u.id)
                print(f"  DELETE {u.original_filename}  "
                      f"({rows:,} rows, {u.uploaded_at:%Y-%m-%d %H:%M})")

        if not doomed:
            print("No duplicate periods found — nothing to clean up.")
            return

        print(f"\n{len(doomed)} superseded report(s), {total_rows:,} duplicate sales rows.")

        if not apply:
            print("\nDry run. Re-run with --apply to delete them.")
            return

        removed = (await db.execute(
            delete(NormalizedSale).where(NormalizedSale.upload_id.in_(doomed))
        )).rowcount
        await db.commit()
        print(f"\nDeleted {removed:,} rows. The report rows and files are untouched.")
        print("Restart the backend and reload the dashboard.")


if __name__ == "__main__":
    asyncio.run(main("--apply" in sys.argv))
