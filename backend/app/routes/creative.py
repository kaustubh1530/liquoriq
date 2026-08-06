"""
routes/creative.py — MODULE 1: AI AD CREATOR endpoints

POST /creative/generate        — Generate a FINISHED ad + platform copy
GET  /creative/{strategy_id}   — Latest ad for that strategy
GET/POST /creative/product-facts — Reusable owner-confirmed product facts

All require JWT auth. Generation calls GPT-4o AND gpt-image-1 — expect 40-60s.

Label/badge endpoints deliberately DO NOT live here: they belong to
routes/label_studio.py (MODULE 2). This module's job ends at a finished ad.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.store import Store
from app.routes.stores import get_current_store
from app.schemas.creative import (
    ComposeRequest,
    CreativeResponse,
    GenerateCreativeRequest,
    PriceSuggestion,
    ProductFactsIn,
)
from app.services.creative_service import (
    compose_final_creative,
    generate_ad_creative,
    get_latest_creative_for_strategy,
    get_price_suggestions,
)

router = APIRouter()


@router.get("/product-facts", summary="Saved facts for a product (Professional Ad Upgrade)")
async def get_product_facts(
    product_name: str,
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.product_facts_service import get_facts
    return {"product_name": product_name, "facts": await get_facts(current_store.id, product_name, db) or {}}


@router.post("/product-facts", summary="Save/confirm reusable product facts")
async def save_product_facts(
    body: ProductFactsIn,
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.product_facts_service import upsert_facts
    row = await upsert_facts(current_store.id, body.product_name, body.category, body.facts, db)
    return {"product_name": row.product_name, "category": row.category, "facts": row.facts}


@router.post(
    "/product-photo",
    summary="Upload a real product photo (saved to the reusable library) (Phase 16)",
)
async def upload_product_photo(
    current_store: Annotated[Store, Depends(get_current_store)],
    file: UploadFile = File(..., description="A photo of the real bottle (JPG/PNG)"),
    product_name: str | None = Form(default=None, description="Save it to the library for this product"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.creative_service import _to_png
    from app.services.product_photo_service import upsert_photo
    from app.services.storage_service import save_image

    raw = await file.read()
    if not raw:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Empty file.")
    try:
        png = _to_png(raw)
    except Exception:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="Could not read that image. Use a JPG or PNG.")
    url = await save_image(png, prefix="product")

    # "Upload once, reuse forever" — remember it for this product
    if product_name and product_name.strip():
        await upsert_photo(current_store.id, product_name.strip(), url, db)

    return {"product_image_url": url}


@router.get(
    "/product-photo",
    summary="The saved library photo for a product, if any (Phase 16)",
)
async def get_product_photo(
    product_name: str,
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.product_photo_service import get_photo_url
    url = await get_photo_url(current_store.id, product_name, db)
    return {"product_image_url": url}


@router.post(
    "/generate",
    response_model=CreativeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate ad image + platform copy for a strategy",
    description=(
        "Takes an existing AI strategy, generates a DALL-E 3 ad image plus "
        "copy tailored for Instagram, Facebook, Uber Eats, DoorDash, and a "
        "website banner. Takes 15-30 seconds. Regenerating creates a new "
        "version; GET returns the newest."
    ),
)
async def generate_creative(
    body: GenerateCreativeRequest,
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> CreativeResponse:
    try:
        creative = await generate_ad_creative(
            strategy_id=body.strategy_id,
            store_id=current_store.id,
            db=db,
            offer_override=body.offer_override,
            instructions=body.instructions,
            product_image_url=body.product_image_url,
            image_format=body.image_format,
            product_facts=body.product_facts,
            campaign_type=body.campaign_type,
            show_product_details=body.show_product_details,
            ad_layout=body.ad_layout,
        )
    except ValueError as e:
        # Strategy not found → 404; bad AI output → 422
        if "not found" in str(e).lower():
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(e))
    return creative


@router.get(
    "/{strategy_id}/prices",
    response_model=list[PriceSuggestion],
    summary="Price prefill for the strategy's promoted products",
    description=(
        "Latest unit_price per promoted product from the store's own sales "
        "data. price is null when the product name has no matching sale row — "
        "the owner fills it in manually."
    ),
)
async def get_prices(
    strategy_id: uuid.UUID,
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> list[PriceSuggestion]:
    try:
        return await get_price_suggestions(
            strategy_id=strategy_id,
            store_id=current_store.id,
            db=db,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/{creative_id}/compose",
    response_model=CreativeResponse,
    summary="Compose the final ad with exact prices overlaid",
    description=(
        "Stamps the owner-confirmed product names and prices onto the AI "
        "background with Pillow — deterministic text, no AI typos. "
        "Returns the creative with final_image_url set. Max 5 rows rendered."
    ),
)
async def compose_creative(
    creative_id: uuid.UUID,
    body: ComposeRequest,
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> CreativeResponse:
    try:
        creative = await compose_final_creative(
            creative_id=creative_id,
            store_id=current_store.id,
            items=[item.model_dump() for item in body.items],
            db=db,
        )
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(e))
    return creative


@router.get(
    "/{strategy_id}",
    response_model=CreativeResponse,
    summary="Latest creative package for a strategy",
)
async def get_creative(
    strategy_id: uuid.UUID,
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> CreativeResponse:
    creative = await get_latest_creative_for_strategy(
        strategy_id=strategy_id,
        store_id=current_store.id,
        db=db,
    )
    if not creative:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="No creative generated for this strategy yet",
        )
    return creative


# ── PHASE 23.6: the campaign context ─────────────────────────────────────────

@router.get(
    "/campaign-context/{strategy_id}",
    summary="Everything a downstream tool needs to act on one campaign",
)
async def campaign_context(
    strategy_id: uuid.UUID,
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    ONE campaign, understood once, read by every tool that acts on it.

    The Ad Creator is the first consumer. Label Studio, the scheduler, social
    posting, SMS and email are the next, and none of them will re-derive any
    of this — if each page inferred its own campaign type, the ad would
    eventually say "Premium Collection" while the shelf label said "Standard"
    for the same campaign.

    Everything is derived deterministically from the strategy plus facts the
    owner has already confirmed. No GPT call: this page should feel instant,
    and a model here would add seconds to a form that is meant to be already
    filled in.
    """
    from sqlalchemy import select

    from app.models.ai_strategy_report import AIStrategyReport
    from app.services import campaign_context as CTX

    strategy = (await db.execute(
        select(AIStrategyReport).where(
            AIStrategyReport.id == strategy_id,
            AIStrategyReport.store_id == current_store.id,
        )
    )).scalar_one_or_none()

    if strategy is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            detail="That campaign does not exist.")

    return await CTX.build(strategy, current_store.id, db)
