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
from app.services.shelf_label import (
    apply_template as merge_template,
    as_template,
    blank_label,
    label_summary,
    validate_label,
)
from app.services.shelf_label_renderer import render_label, render_sheet, render_sheet_preview
from app.services.storage_service import save_image

logger = logging.getLogger(__name__)


async def list_labels(
    store_id: uuid.UUID, db: AsyncSession, strategy_id: uuid.UUID | None = None
) -> list[LabelDesign]:
    """
    This store's saved labels (not templates), most recently edited first.

    With `strategy_id`, only the labels made for that campaign. Filtering here
    rather than in the caller keeps the store scope and the campaign scope in
    the same WHERE clause — they are both auth-shaped and both easy to forget.
    """
    query = (
        select(LabelDesign)
        .where(LabelDesign.store_id == store_id, LabelDesign.is_template.is_(False))
        .order_by(LabelDesign.updated_at.desc())
    )
    if strategy_id is not None:
        query = query.where(LabelDesign.strategy_id == strategy_id)
    result = await db.execute(query)
    return list(result.scalars().all())


async def count_labels(
    store_id: uuid.UUID, db: AsyncSession, strategy_id: uuid.UUID | None = None
) -> int:
    """How many saved labels — for one campaign, or for the whole store."""
    query = select(func.count(LabelDesign.id)).where(
        LabelDesign.store_id == store_id, LabelDesign.is_template.is_(False)
    )
    if strategy_id is not None:
        query = query.where(LabelDesign.strategy_id == strategy_id)
    return int((await db.execute(query)).scalar_one() or 0)


async def list_templates(store_id: uuid.UUID, db: AsyncSession) -> list[LabelDesign]:
    """Saved STYLES, reusable across products."""
    result = await db.execute(
        select(LabelDesign)
        .where(LabelDesign.store_id == store_id, LabelDesign.is_template.is_(True))
        .order_by(LabelDesign.updated_at.desc())
    )
    return list(result.scalars().all())


async def save_as_template(
    store_id: uuid.UUID, db: AsyncSession, spec: dict, name: str = ""
) -> LabelDesign:
    """Keep the LOOK, drop the product. That's what makes it reusable."""
    template = as_template(spec, name)
    row = LabelDesign(
        store_id=store_id,
        name=template.get("template_name") or "Untitled style",
        base_image_url=None,
        design_json=template,
        is_template=True,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    logger.info("Label template saved: id=%s name=%s", row.id, row.name)
    return row


async def apply_template_to(
    template_id: uuid.UUID, store_id: uuid.UUID, spec: dict, db: AsyncSession
) -> dict:
    """Return the caller's CONTENT rendered in the template's LOOK."""
    template = await get_label(template_id, store_id, db)
    return merge_template(template.design_json, spec)


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
    store_id: uuid.UUID, db: AsyncSession, spec: dict | None = None,
    strategy_id: uuid.UUID | None = None,
) -> LabelDesign:
    """
    A new label, optionally belonging to a campaign.

    `strategy_id` is recorded at CREATION and never inferred later: the only
    moment we honestly know which campaign a label was made for is the moment
    the owner made it from inside that campaign.
    """
    label = validate_label(spec) if spec else blank_label()
    row = LabelDesign(
        store_id=store_id,
        name=label_summary(label)[:200],
        base_image_url=None,          # shelf labels draw their own background
        design_json=label,
        strategy_id=strategy_id,
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


async def _specs_for(label_ids, store_id, db) -> list[dict]:
    """The chosen labels, store-scoped and in the order the owner picked them."""
    if not label_ids:
        raise ValueError("Select at least one label to print.")
    result = await db.execute(
        select(LabelDesign).where(
            LabelDesign.id.in_(label_ids), LabelDesign.store_id == store_id
        )
    )
    rows = [r for r in result.scalars().all() if not r.is_template]
    if not rows:
        raise ValueError("None of those labels were found.")
    order = {lid: i for i, lid in enumerate(label_ids)}
    rows.sort(key=lambda r: order.get(r.id, 0))
    return [r.design_json for r in rows]


async def sheet_for_labels(
    label_ids: list[uuid.UUID], store_id: uuid.UUID, db: AsyncSession,
    per_page: int = 4, page: str = "a4", repeat: bool = False, cut_marks: bool = True,
    orientation: str = "landscape",
) -> bytes:
    """
    A printable PDF with `per_page` labels on each sheet. Store-scoped: ids
    belonging to another store simply aren't found, so nothing leaks.
    """
    specs = await _specs_for(label_ids, store_id, db)
    return await render_sheet(specs, per_page, page, repeat, cut_marks, orientation)


async def sheet_preview_for_labels(
    label_ids: list[uuid.UUID], store_id: uuid.UUID, db: AsyncSession,
    per_page: int = 4, page: str = "a4", repeat: bool = False, cut_marks: bool = True,
    orientation: str = "landscape",
) -> bytes:
    """PNG of page 1 — check the arrangement before spending paper."""
    specs = await _specs_for(label_ids, store_id, db)
    return await render_sheet_preview(specs, per_page, page, repeat, cut_marks, orientation)


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
