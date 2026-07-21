"""
routes/stores.py — Store profiles, multi-store selection, staff management

Phase 14 redesign (one owner → many stores; staff pinned to one store):

POST /stores                    — owner creates a(nother) store
GET  /stores                    — list all stores the user can access
GET  /stores/me                 — the CURRENTLY SELECTED store
PUT  /stores/me                 — update the currently selected store (owner only)
POST /stores/{store_id}/staff   — owner creates a staff login for that store
GET  /stores/{store_id}/staff   — owner lists staff of that store
DELETE /stores/staff/{user_id}  — owner deactivates a staff account

STORE SELECTION:
  - staff: always their pinned store (users.store_id) — no choice.
  - owner: the X-Store-Id request header picks the store (validated against
    ownership); without the header, the first (oldest) store is used.
  The frontend axios client sends X-Store-Id automatically once a store is
  chosen in the switcher, so every existing endpoint (uploads, analytics, AI,
  creative, transfers) is store-scoped with zero changes to those routers.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Store, User
from app.routes.auth import get_current_user
from app.schemas.user import (
    StaffCreate,
    StaffResponse,
    StoreCreate,
    StoreResponse,
    StoreUpdate,
)
from app.utils.security import hash_password

router = APIRouter()


# ─── Core dependency: resolve the ACTIVE store for this request ───────────────

async def get_current_store(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
    x_store_id: Annotated[str | None, Header(alias="X-Store-Id")] = None,
) -> Store:
    """
    Staff → their pinned store. Owner → X-Store-Id header (must be a store
    they own) or their first store. 400 if the user has no store at all.
    """
    if current_user.role == "staff":
        if current_user.store_id is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                detail="Staff account is not assigned to a store. Ask the owner.")
        result = await db.execute(select(Store).where(Store.id == current_user.store_id))
        store = result.scalar_one_or_none()
        if store is None or not store.is_active:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Assigned store not found.")
        return store

    # Owner path
    if x_store_id:
        try:
            wanted = uuid.UUID(x_store_id)
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid X-Store-Id header.")
        result = await db.execute(
            select(Store).where(Store.id == wanted, Store.owner_id == current_user.id)
        )
        store = result.scalar_one_or_none()
        if store is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                detail="That store does not belong to your account.")
        return store

    result = await db.execute(
        select(Store)
        .where(Store.owner_id == current_user.id)
        .order_by(Store.created_at)
        .limit(1)
    )
    store = result.scalar_one_or_none()
    if store is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="You must create a store profile first. Use POST /stores.",
        )
    return store


def _require_owner(user: User) -> None:
    if user.role != "owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Owner account required.")


# ─── Store CRUD ───────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=StoreResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a store (owners can have several)",
)
async def create_store(
    store_data: StoreCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> Store:
    _require_owner(current_user)
    new_store = Store(owner_id=current_user.id, **store_data.model_dump())
    db.add(new_store)
    await db.flush()
    await db.refresh(new_store)
    return new_store


@router.get(
    "",
    response_model=list[StoreResponse],
    summary="List all stores this account can access",
)
async def list_stores(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> list[Store]:
    if current_user.role == "staff":
        result = await db.execute(select(Store).where(Store.id == current_user.store_id))
        return list(result.scalars().all())
    result = await db.execute(
        select(Store).where(Store.owner_id == current_user.id).order_by(Store.created_at)
    )
    return list(result.scalars().all())


@router.get(
    "/me",
    response_model=StoreResponse,
    summary="Get the currently selected store",
)
async def get_my_store(
    store: Annotated[Store, Depends(get_current_store)],
) -> Store:
    return store


@router.put(
    "/me",
    response_model=StoreResponse,
    summary="Update the currently selected store (owner only)",
)
async def update_my_store(
    store_data: StoreUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> Store:
    _require_owner(current_user)
    update_data = store_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(store, field, value)
    await db.flush()
    await db.refresh(store)
    return store


# ─── Staff management (owner only) ────────────────────────────────────────────

@router.post(
    "/{store_id}/staff",
    response_model=StaffResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a staff login pinned to one store",
)
async def create_staff(
    store_id: uuid.UUID,
    body: StaffCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> User:
    _require_owner(current_user)

    # The store must belong to this owner
    result = await db.execute(
        select(Store).where(Store.id == store_id, Store.owner_id == current_user.id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            detail="That store does not belong to your account.")

    # Email must be free
    existing = await db.execute(select(User).where(User.email == body.email.lower()))
    if existing.scalar_one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT,
                            detail="An account with this email already exists.")

    staff = User(
        email=body.email.lower(),
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
        role="staff",
        store_id=store_id,
    )
    db.add(staff)
    await db.flush()
    await db.refresh(staff)
    return staff


@router.get(
    "/{store_id}/staff",
    response_model=list[StaffResponse],
    summary="List staff accounts of one store",
)
async def list_staff(
    store_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> list[User]:
    _require_owner(current_user)
    owned = await db.execute(
        select(Store).where(Store.id == store_id, Store.owner_id == current_user.id)
    )
    if owned.scalar_one_or_none() is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            detail="That store does not belong to your account.")
    result = await db.execute(
        select(User).where(User.store_id == store_id, User.role == "staff")
        .order_by(User.created_at)
    )
    return list(result.scalars().all())


@router.delete(
    "/staff/{user_id}",
    response_model=StaffResponse,
    summary="Deactivate a staff account",
)
async def deactivate_staff(
    user_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db),
) -> User:
    _require_owner(current_user)
    result = await db.execute(select(User).where(User.id == user_id, User.role == "staff"))
    staff = result.scalar_one_or_none()
    if staff is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Staff account not found.")

    # Their store must belong to this owner
    owned = await db.execute(
        select(Store).where(Store.id == staff.store_id, Store.owner_id == current_user.id)
    )
    if owned.scalar_one_or_none() is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            detail="That staff account is not in your stores.")

    staff.is_active = False
    await db.flush()
    await db.refresh(staff)
    return staff
