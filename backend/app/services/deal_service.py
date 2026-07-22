"""services/deal_service.py — Supplier deal-buy CRUD (Phase 15)"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deal_buy import DealBuy


async def create_deal(store_id: uuid.UUID, data: dict, db: AsyncSession) -> DealBuy:
    deal = DealBuy(store_id=store_id, **data)
    db.add(deal)
    await db.commit()
    await db.refresh(deal)
    return deal


async def list_deals(store_id: uuid.UUID, db: AsyncSession, active_only: bool = True) -> list[DealBuy]:
    query = select(DealBuy).where(DealBuy.store_id == store_id)
    if active_only:
        query = query.where(DealBuy.is_active.is_(True))
    query = query.order_by(DealBuy.created_at.desc())
    result = await db.execute(query)
    return list(result.scalars().all())


async def deactivate_deal(store_id: uuid.UUID, deal_id: uuid.UUID, db: AsyncSession) -> None:
    result = await db.execute(
        select(DealBuy).where(DealBuy.id == deal_id, DealBuy.store_id == store_id)
    )
    deal = result.scalar_one_or_none()
    if deal is None:
        raise ValueError("Deal not found.")
    deal.is_active = False
    await db.commit()
