"""services/product_photo_service.py — Product photo library (Phase 16)"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product_photo import ProductPhoto


def _key(product_name: str) -> str:
    return product_name.strip().lower()


async def upsert_photo(store_id: uuid.UUID, product_name: str, image_url: str, db: AsyncSession) -> ProductPhoto:
    """Save (or replace) the photo for a product in this store's library."""
    key = _key(product_name)
    result = await db.execute(
        select(ProductPhoto).where(
            ProductPhoto.store_id == store_id, ProductPhoto.product_key == key
        )
    )
    photo = result.scalar_one_or_none()
    if photo:
        photo.image_url = image_url
        photo.product_name = product_name.strip()
    else:
        photo = ProductPhoto(
            store_id=store_id, product_key=key,
            product_name=product_name.strip(), image_url=image_url,
        )
        db.add(photo)
    await db.commit()
    await db.refresh(photo)
    return photo


async def get_photo_url(store_id: uuid.UUID, product_name: str, db: AsyncSession) -> str | None:
    if not product_name:
        return None
    result = await db.execute(
        select(ProductPhoto.image_url).where(
            ProductPhoto.store_id == store_id, ProductPhoto.product_key == _key(product_name)
        )
    )
    return result.scalar_one_or_none()
