"""
services/label_design_service.py — MODULE 2: LABEL STUDIO (DB operations)

Every function is store-scoped: a label is only ever readable or writable by the
store that owns it. This is the auth boundary for the whole module.
"""

import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.label_design import LabelDesign
from app.models.normalized_sale import NormalizedSale
from app.services.shelf_label import blank_label, label_summary, validate_label
from app.services.shelf_label_renderer import render_label, render_sheet
from app.services.storage_service import save_image

logger = logging.getLogger(__name__)


async def list_labels(store_id: uuid.UUID, db: AsyncSession) -> list[LabelDesign]:
    """All of this store's saved labels, most recently edited first."""
    result = await db.execute(
        select(LabelDesign)
        .where(LabelDesign.store_id == store_id)
        .order_by(LabelDesign.updated_at.desc())
    )
    return list(result.scalars().all())


async def get_label(label_id: uuid.UUID, store_id: uuid.UUID, db: AsyncSession) -> LabelDesign:
    result = await db.execute(
        select(LabelDesign).where(
            LabelDesign.id == label_id, LabelDesign.store_id == store_id
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise ValueError("Label not found")
    return row


async def create_label(
    store_id: uuid.UUID, db: AsyncSession, spec: dict | None = None
) -> LabelDesign:
    label = validate_label(spec) if spec else blank_label()
    row = LabelDesign(
        store_id=store_id,
        name=label_summary(label)[:200],
        base_image_url=None,          # shelf labels draw their own background
        design_json=label,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    logger.info("Shelf label created: id=%s", row.id)
    return row


async def save_label(
    label_id: uuid.UUID, store_id: uuid.UUID, spec: dict, db: AsyncSession
) -> LabelDesign:
    row = await get_label(label_id, store_id, db)
    label = validate_label(spec)
    row.design_json = label
    row.name = label_summary(label)[:200]
    await db.commit()
    await db.refresh(row)
    return row


async def delete_label(label_id: uuid.UUID, store_id: uuid.UUID, db: AsyncSession) -> None:
    row = await get_label(label_id, store_id, db)
    await db.delete(row)
    await db.commit()


async def export_label(
    label_id: uuid.UUID, store_id: uuid.UUID, db: AsyncSession
) -> LabelDesign:
    """Render the label to a PNG and store it (local disk in dev, Cloudinary in prod)."""
    row = await get_label(label_id, store_id, db)
    png = await render_label(row.design_json)
    row.final_image_url = await save_image(png, prefix="label")
    await db.commit()
    await db.refresh(row)
    logger.info("Shelf label exported: id=%s url=%s", row.id, row.final_image_url)
    return row


async def sheet_for_labels(
    label_ids: list[uuid.UUID], store_id: uuid.UUID, db: AsyncSession, size: str | None = None
) -> bytes:
    """
    A printable US Letter PDF of the chosen labels. Store-scoped: ids belonging
    to another store are simply not found, so nothing leaks across tenants.
    """
    if not label_ids:
        raise ValueError("Select at least one label to print.")
    result = await db.execute(
        select(LabelDesign).where(
            LabelDesign.id.in_(label_ids), LabelDesign.store_id == store_id
        )
    )
    rows = list(result.scalars().all())
    if not rows:
        raise ValueError("None of those labels were found.")

    # Preserve the order the owner selected them in
    order = {lid: i for i, lid in enumerate(label_ids)}
    rows.sort(key=lambda r: order.get(r.id, 0))

    specs = [r.design_json for r in rows]
    sheet_size = size or specs[0].get("size", "medium")
    return await render_sheet(specs, sheet_size)


async def product_suggestions(
    store_id: uuid.UUID, db: AsyncSession, limit: int = 40
) -> list[dict]:
    """
    Products from the store's OWN sales data, with the latest price seen.

    This is the moat in miniature applied to a mundane task: the owner picks a
    bottle and the name and price are already filled in, because we have their
    POS history. No generic label maker can do that.
    """
    latest = (
        select(
            NormalizedSale.product_name.label("name"),
            func.max(NormalizedSale.sale_date).label("last_sold"),
            func.sum(NormalizedSale.quantity).label("units"),
        )
        .where(NormalizedSale.store_id == store_id)
        .group_by(NormalizedSale.product_name)
        .order_by(func.sum(NormalizedSale.quantity).desc())
        .limit(limit)
        .subquery()
    )
    rows = await db.execute(select(latest.c.name, latest.c.units))

    out: list[dict] = []
    for name, units in rows.all():
        price_row = await db.execute(
            select(NormalizedSale.unit_price)
            .where(
                NormalizedSale.store_id == store_id,
                NormalizedSale.product_name == name,
                NormalizedSale.unit_price.isnot(None),
            )
            .order_by(NormalizedSale.sale_date.desc())
            .limit(1)
        )
        price = price_row.scalar_one_or_none()
        out.append({
            "product_name": str(name),
            "price": f"${float(price):,.2f}" if price is not None else "",
            "units_sold": int(units or 0),
        })
    return out
