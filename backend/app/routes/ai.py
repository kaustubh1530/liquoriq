"""
routes/ai.py — AI Promotion Strategy endpoints

POST /ai/generate-promotion   — Generate and save a new AI strategy
GET  /ai/strategies           — List all past strategies (newest first)
GET  /ai/strategies/{id}      — Full detail view of one strategy

All endpoints require JWT auth (get_current_store dependency).
Generation hits the OpenAI API — expect 3-8s response time for GPT-4o.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.store import Store
from app.routes.stores import get_current_store
from app.schemas.strategy import (
    GeneratePromotionRequest,
    StrategyListItem,
    StrategyResponse,
)
from app.services.strategy_service import (
    generate_promotion_strategy,
    get_all_strategies,
    get_strategy_by_id,
)

router = APIRouter()


@router.post(
    "/generate-promotion",
    response_model=StrategyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a new AI promotion strategy for slow-moving products",
    description=(
        "Fetches the store's slowest-selling products, sends them to GPT-4o, "
        "and returns a full promotion campaign (SMS copy, email, social caption, etc.). "
        "The result is saved to the database and visible in GET /ai/strategies."
    ),
)
async def generate_promotion(
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
    body: GeneratePromotionRequest = GeneratePromotionRequest(),
) -> StrategyResponse:
    try:
        report = await generate_promotion_strategy(
            store_id=current_store.id,
            db=db,
            limit=body.limit,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        )
    return report


@router.get(
    "/strategies",
    response_model=list[StrategyListItem],
    summary="List all past AI strategies (newest first)",
)
async def list_strategies(
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> list[StrategyListItem]:
    return await get_all_strategies(store_id=current_store.id, db=db)


@router.get(
    "/strategies/{strategy_id}",
    response_model=StrategyResponse,
    summary="Full detail of a single strategy",
)
async def get_strategy(
    strategy_id: uuid.UUID,
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> StrategyResponse:
    report = await get_strategy_by_id(
        strategy_id=strategy_id,
        store_id=current_store.id,
        db=db,
    )
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Strategy not found",
        )
    return report