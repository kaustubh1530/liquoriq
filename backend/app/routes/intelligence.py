"""
routes/intelligence.py — PHASE 22: Business Intelligence API

GET  /intelligence                  the whole Executive Dashboard payload
GET  /intelligence/actions          just the Action Center
GET  /intelligence/opportunities    ranked growth opportunities
GET  /intelligence/categories       category intelligence
GET  /intelligence/inventory        product-level metrics (filterable)
POST /intelligence/explain          AI prose for ONE already-computed action
POST /intelligence/category-override  the owner corrects a category (tier 1)

Every number returned by every endpoint here is computed deterministically.
The single AI endpoint takes a FINISHED action and returns prose; it cannot
change a figure, and if OpenAI is unavailable it returns deterministic text.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.product_category import ProductCategory
from app.models.store import Store
from app.routes.stores import get_current_store
from app.services.bi import categorizer as CAT
from app.services.bi import explain as EXPLAIN
from app.services.bi import reorder as REORDER
from app.services.bi.engine import build_intelligence

router = APIRouter()


@router.get("", summary="The complete Executive Dashboard payload")
async def get_intelligence(
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Business health, action center, opportunities, category intelligence,
    inventory distribution and per-product metrics — one call, one render.
    Entirely deterministic; no AI is involved in producing any of it.
    """
    return await build_intelligence(current_store.id, db)


@router.get("/actions", summary="Today's Action Center")
async def get_actions(
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = await build_intelligence(current_store.id, db)
    return {
        "business_health": data["business_health"],
        "headline": data["headline"],
        "actions": data["actions"],
        "priority_counts": data["priority_counts"],
        "assumptions": data["assumptions"],
    }


@router.get("/opportunities", summary="Growth opportunities, ranked by value")
async def get_opportunities(
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = await build_intelligence(current_store.id, db)
    return {"opportunities": data["opportunities"], "headline": data["headline"]}


@router.get("/categories", summary="Category intelligence")
async def get_categories(
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = await build_intelligence(current_store.id, db)
    return {"categories": data["categories"], "coverage": data["coverage"]}


@router.get("/inventory", summary="Product-level inventory intelligence")
async def get_inventory(
    current_store: Annotated[Store, Depends(get_current_store)],
    stock_class: str | None = Query(None, description="Filter to one stock class"),
    category: str | None = Query(None),
    limit: int = Query(100, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = await build_intelligence(current_store.id, db)
    products = data["products"]
    if stock_class:
        products = [p for p in products if p["stock_class"] == stock_class]
    if category:
        products = [p for p in products if (p.get("category") or "Other") == category]
    return {
        "products": products[:limit],
        "total_matching": len(products),
        "summary": data["summary"],
        "period": data["period"],
    }


@router.get("/reorder-list", summary="A purchase list the owner can hand to a rep")
async def get_reorder_list(
    current_store: Annotated[Store, Depends(get_current_store)],
    horizon_weeks: float = Query(None, gt=0, le=52,
                                 description="Weeks of demand to cover; defaults to the engine assumption"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    "1,128 products need reordering" is a finding. THIS is the action: what to
    buy, how many, and what it is worth — net of stock already on hand.

    The money column is RETAIL value, not cost. The POS export has no cost
    price, and labelling a retail figure as cost would overstate the owner's
    outlay by his whole margin.
    """
    data = await build_intelligence(current_store.id, db)
    rows = REORDER.build_reorder_list(data["products"], horizon_weeks)
    return {
        "items": rows,
        "totals": REORDER.summarise(rows, horizon_weeks),
        "period": data["period"],
        "columns": [{"key": k, "label": v} for k, v in REORDER.CSV_COLUMNS],
        "disclaimer": (
            "Quantities cover the horizon net of stock on hand. Values are at "
            "RETAIL price — your POS export contains no cost data, so this is "
            "not what the order will cost you."
        ),
    }


# ── The AI layer — prose only ────────────────────────────────────────────────

class ExplainIn(BaseModel):
    """
    A FINISHED action, as returned by /intelligence/actions.

    The model receives only these already-computed values. There is no path by
    which it could recalculate anything, because it never sees the sales rows.
    """
    action: dict = Field(description="One action object from the Action Center")


@router.post("/explain", summary="Explain one computed action in business English")
async def explain(
    body: ExplainIn,
    current_store: Annotated[Store, Depends(get_current_store)],
) -> dict:
    """
    GPT explains; it never calculates. Any figure in the response that we did
    not supply causes the explanation to be discarded in favour of
    deterministic text, so a hallucinated number cannot reach the owner.
    """
    if not body.action:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="An action object is required.")
    return {"explanation": await EXPLAIN.explain_action(body.action)}


# ── Category override — tier 1 of the cascade ────────────────────────────────

class CategoryOverrideIn(BaseModel):
    product_key: str = Field(min_length=1, max_length=200,
                             description="SKU/UPC, or the product name if no SKU")
    product_name: str = Field(default="", max_length=500)
    category: str
    brand: str | None = Field(default=None, max_length=80)


@router.post("/category-override", status_code=status.HTTP_201_CREATED,
             summary="Correct a product's category (permanent, beats every other tier)")
async def override_category(
    body: CategoryOverrideIn,
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    if body.category not in CAT.CATEGORIES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Category must be one of: {', '.join(CAT.CATEGORIES)}",
        )

    existing = (await db.execute(
        select(ProductCategory).where(
            ProductCategory.store_id == current_store.id,
            ProductCategory.product_key == body.product_key,
        )
    )).scalar_one_or_none()

    if existing:
        existing.category = body.category
        existing.brand = body.brand
        existing.source = "manual"
        existing.confidence = "certain"
        if body.product_name:
            existing.product_name = body.product_name
        row = existing
    else:
        row = ProductCategory(
            store_id=current_store.id, product_key=body.product_key,
            product_name=body.product_name, category=body.category,
            brand=body.brand, source="manual", confidence="certain",
        )
        db.add(row)

    await db.commit()
    await db.refresh(row)
    return {"product_key": row.product_key, "category": row.category,
            "source": row.source, "confidence": row.confidence}


class MarginIn(BaseModel):
    gross_margin_pct: int | None = Field(
        default=None, ge=0, le=95,
        description="Owner's gross margin %. Null or 0 clears it back to retail-only.",
    )


@router.post("/gross-margin", summary="Set the store's gross margin")
async def set_gross_margin(
    body: MarginIn,
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Turns retail figures into cash figures.

    Without it the dashboard shows RETAIL values and labels them as such. We do
    not substitute an industry average: a number the owner didn't give us is
    not his number, and presenting one as his is how a dashboard loses its
    credibility on the figure he checks first.
    """
    from app.services.bi import valuation as VAL

    margin = VAL.normalise_margin(body.gross_margin_pct)
    current_store.gross_margin_pct = margin
    await db.commit()
    return {
        "gross_margin_pct": margin,
        "basis": "cost" if margin else "retail",
    }


@router.get("/category-options", summary="The fixed category list")
async def category_options() -> dict:
    """The list GPT and the owner may both choose from. Nothing invents a category."""
    return {"categories": CAT.CATEGORIES, "non_product": CAT.NON_PRODUCT}
