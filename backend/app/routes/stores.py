"""
routes/stores.py — Store profile endpoints

POST /stores      — create the store profile for the logged-in user
GET  /stores/me   — get the logged-in user's store
PUT  /stores/me   — update the logged-in user's store

Design: one user → one store (MVP). Every upload, analytics query, and
AI strategy is scoped to a store, so this must exist before Phase 4b
(report uploads) can work.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Store, User
from app.routes.auth import get_current_user
from app.schemas.user import StoreCreate, StoreResponse, StoreUpdate

router = APIRouter()


@router.post(
    "",
    response_model=StoreResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create the store profile for the logged-in user",
)
async def create_store(
    store_data: StoreCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> Store:
    # Enforce one store per user (MVP constraint)
    result = await db.execute(select(Store).where(Store.owner_id == current_user.id))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This account already has a store. Use PUT /stores/me to update it.",
        )

    new_store = Store(owner_id=current_user.id, **store_data.model_dump())
    db.add(new_store)
    await db.flush()
    await db.refresh(new_store)

    return new_store


@router.get(
    "/me",
    response_model=StoreResponse,
    summary="Get the logged-in user's store",
)
async def get_my_store(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> Store:
    result = await db.execute(select(Store).where(Store.owner_id == current_user.id))
    store = result.scalar_one_or_none()

    if store is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No store found for this account. Create one with POST /stores.",
        )

    return store


@router.put(
    "/me",
    response_model=StoreResponse,
    summary="Update the logged-in user's store",
)
async def update_my_store(
    store_data: StoreUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> Store:
    result = await db.execute(select(Store).where(Store.owner_id == current_user.id))
    store = result.scalar_one_or_none()

    if store is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No store found for this account. Create one with POST /stores.",
        )

    # Only update fields the client actually sent (exclude_unset=True)
    update_data = store_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(store, field, value)

    await db.flush()
    await db.refresh(store)

    return store


# ─── Internal helper used by other routers (e.g. uploads.py) ─────────────────
# Not exposed as an endpoint — just a reusable dependency.

async def get_current_store(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> Store:
    """
    Dependency that resolves the logged-in user's store.
    Raises 400 if they haven't created one yet — every upload/analytics
    route needs a store to scope data to.
    """
    result = await db.execute(select(Store).where(Store.owner_id == current_user.id))
    store = result.scalar_one_or_none()

    if store is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You must create a store profile before uploading reports. "
                   "Use POST /stores first.",
        )

    return store