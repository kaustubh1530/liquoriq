"""services/product_facts_service.py — Reusable product facts (Professional Ad Upgrade)"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product_facts import ProductFacts


def _key(product_name: str) -> str:
    return product_name.strip().lower()


async def upsert_facts(
    store_id: uuid.UUID, product_name: str, category: str | None, facts: dict, db: AsyncSession,
) -> ProductFacts:
    key = _key(product_name)
    result = await db.execute(
        select(ProductFacts).where(ProductFacts.store_id == store_id, ProductFacts.product_key == key)
    )
    row = result.scalar_one_or_none()
    # keep only non-empty confirmed facts
    clean = {k: v for k, v in (facts or {}).items() if v not in (None, "", [])}
    if row:
        row.facts = clean
        row.product_name = product_name.strip()
        row.category = category or row.category
    else:
        row = ProductFacts(
            store_id=store_id, product_key=key, product_name=product_name.strip(),
            category=category, facts=clean,
        )
        db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def get_facts(store_id: uuid.UUID, product_name: str, db: AsyncSession) -> dict | None:
    if not product_name:
        return None
    result = await db.execute(
        select(ProductFacts).where(ProductFacts.store_id == store_id, ProductFacts.product_key == _key(product_name))
    )
    row = result.scalar_one_or_none()
    return row.facts if row else None
