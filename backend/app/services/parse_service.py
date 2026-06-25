"""
services/parse_service.py — Orchestrates the full parse workflow

Flow:
  1. Load the UploadedReport record → get file_path and source
  2. Set status = processing
  3. Pick the right parser from the registry
  4. Run parser.parse(file_path) → list of row dicts
  5. Bulk-insert rows into normalized_sales
  6. Set status = completed + rows_processed count
  7. On any error → set status = failed + error_message

This service is called from the route layer (POST /uploads/{id}/parse).
It can also be called from a background task or queue in the future.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.normalized_sale import NormalizedSale
from app.models.uploaded_report import ReportStatus, UploadedReport
from app.services.parsers.registry import get_parser


async def parse_upload(upload_id: uuid.UUID, store_id: uuid.UUID, db: AsyncSession) -> UploadedReport:
    """
    Parse an uploaded report and persist normalized rows.

    Args:
        upload_id: UUID of the UploadedReport to process
        store_id:  UUID of the store (used as ownership guard)
        db:        Active async database session

    Returns:
        The updated UploadedReport record (status = completed or failed)

    Raises:
        ValueError: if the upload doesn't exist or doesn't belong to the store
    """
    # ── 1. Fetch the upload record ─────────────────────────────────────────────
    result = await db.execute(
        select(UploadedReport).where(
            UploadedReport.id == upload_id,
            UploadedReport.store_id == store_id,
        )
    )
    upload = result.scalar_one_or_none()

    if upload is None:
        raise ValueError("Upload not found or does not belong to your store.")

    if upload.status == ReportStatus.PROCESSING:
        raise ValueError("This upload is already being processed.")

    if upload.status == ReportStatus.COMPLETED:
        raise ValueError(
            "This upload has already been processed. "
            "If you want to re-parse it, delete the existing normalized data first."
        )

    # ── 2. Mark as processing ──────────────────────────────────────────────────
    upload.status = ReportStatus.PROCESSING
    await db.flush()

    try:
        # ── 3. Pick parser and run it ──────────────────────────────────────────
        parser = get_parser(upload.source)
        rows = parser.parse(upload.file_path)

        if not rows:
            raise ValueError("Parser returned 0 rows. Check that the file has data.")

        # ── 4. Bulk-insert normalized rows ─────────────────────────────────────
        sale_objects = [
            NormalizedSale(
                store_id=store_id,
                upload_id=upload_id,
                product_name=row["product_name"],
                sku=row.get("sku"),
                category=row.get("category"),
                quantity=row.get("quantity"),
                unit_price=row.get("unit_price"),
                total_amount=row.get("total_amount"),
                sale_date=row.get("sale_date"),
                channel=row.get("channel", "pos"),
                customer_name=row.get("customer_name"),
                customer_email=row.get("customer_email"),
                customer_phone=row.get("customer_phone"),
                raw_row={
                    k: str(v) if v is not None else None
                    for k, v in (row.get("raw_row") or {}).items()
                },
            )
            for row in rows
        ]
        db.add_all(sale_objects)

        # ── 5. Mark as completed ───────────────────────────────────────────────
        upload.status = ReportStatus.COMPLETED
        upload.rows_processed = len(sale_objects)
        upload.processed_at = datetime.now(timezone.utc)
        upload.error_message = None

    except Exception as e:
        # ── 6. Mark as failed with message ────────────────────────────────────
        upload.status = ReportStatus.FAILED
        upload.error_message = str(e)
        upload.processed_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(upload)
    return upload