"""
routes/deals.py — Supplier deal-buy endpoints (Phase 15)

POST   /deals          — record a closeout/deal buy
GET    /deals          — list active deals
DELETE /deals/{id}     — deactivate (used up / expired)
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.store import Store
from app.routes.stores import get_current_store
from app.schemas.deal import DealCreate, DealResponse
from app.services.deal_service import create_deal, deactivate_deal, list_deals

router = APIRouter()


@router.post("", response_model=DealResponse, status_code=status.HTTP_201_CREATED,
             summary="Record a supplier closeout / deal buy")
async def create(
    body: DealCreate,
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> DealResponse:
    return await create_deal(current_store.id, body.model_dump(), db)


@router.get("", response_model=list[DealResponse], summary="List active deal buys")
async def index(
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> list[DealResponse]:
    return await list_deals(current_store.id, db)


@router.delete("/{deal_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Deactivate a deal buy")
async def remove(
    deal_id: uuid.UUID,
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await deactivate_deal(current_store.id, deal_id, db)
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))
