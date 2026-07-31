"""
routes/campaigns.py — Campaign distribution (Phase 21)

GET  /campaigns/preview        — recipient count + sample + warnings (no send)
POST /campaigns/send           — send to opted-in customers (owner only)
GET  /campaigns                — send history
POST /customers/{id}/opt-out   — suppress a customer (lives here for grouping)

Only opted-in, non-suppressed customers are ever contacted. SMS is a dry run
unless Twilio is configured. No messages are sent without an explicit POST.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.store import Store
from app.models.user import User
from app.routes.auth import get_current_user
from app.routes.stores import get_current_store
from app.services.campaign_delivery_service import (
    list_campaigns,
    preview_campaign,
    send_campaign,
)
from app.services.customer_service import opt_out

router = APIRouter()


class SendRequest(BaseModel):
    strategy_id: uuid.UUID
    channel: str  # sms | email


def _check_channel(channel: str) -> None:
    if channel not in ("sms", "email"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="channel must be 'sms' or 'email'")


@router.get("/preview", summary="Preview a campaign: recipients + sample + warnings (no send)")
async def preview(
    strategy_id: uuid.UUID,
    channel: str,
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    _check_channel(channel)
    try:
        return await preview_campaign(strategy_id, current_store.id, channel, db)
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/send", status_code=status.HTTP_201_CREATED,
             summary="Send a strategy's copy to opted-in customers (owner only)")
async def send(
    body: SendRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    if current_user.role != "owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Only the owner can send campaigns.")
    _check_channel(body.channel)
    try:
        return await send_campaign(
            body.strategy_id, current_store.id, current_user.id, body.channel, db,
            store_name=current_store.name,
        )
    except ValueError as e:
        code = status.HTTP_404_NOT_FOUND if "not found" in str(e).lower() else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(code, detail=str(e))


@router.get("", summary="Campaign send history")
async def history(
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await list_campaigns(current_store.id, db)


@router.post("/opt-out/{customer_id}", status_code=status.HTTP_204_NO_CONTENT,
             summary="Suppress a customer from a channel (opt-out)")
async def customer_opt_out(
    customer_id: uuid.UUID,
    channel: str = Query(..., pattern="^(sms|email)$"),
    current_store: Annotated[Store, Depends(get_current_store)] = None,
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await opt_out(current_store.id, customer_id, channel, db)
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))
