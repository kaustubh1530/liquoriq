"""
routes/label_studio.py — MODULE 2: LABEL STUDIO endpoints

GET    /label-studio/options            — sizes, themes, icons, rating kinds
GET    /label-studio/products           — prefill from the store's own sales data
POST   /label-studio/preview            — live PNG preview of an unsaved spec
GET    /label-studio/labels             — saved labels
POST   /label-studio/labels             — create
GET    /label-studio/labels/{id}        — reopen
PUT    /label-studio/labels/{id}        — save edits
POST   /label-studio/labels/{id}/export — render + store the PNG
DELETE /label-studio/labels/{id}        — delete
POST   /label-studio/sheet              — printable US Letter PDF of many labels

Every route is store-scoped. This module never calls the AI.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.store import Store
from app.routes.stores import get_current_store
from app.schemas.label_studio import LabelIn, LabelOut, ProductSuggestion, SheetIn
from app.services import label_design_service as svc
from app.services.shelf_label import (
    DEFAULT_ICON,
    DEFAULT_SIZE,
    DEFAULT_THEME,
    ICONS,
    LABEL_SIZES,
    POINTS_MAX,
    POINTS_MIN,
    STARS_MAX,
    THEMES,
    blank_label,
)
from app.services.shelf_label_renderer import DRAWABLE_ICONS, labels_per_page, render_label

router = APIRouter()


@router.get("/options", summary="Sizes, themes and icons the label editor offers")
async def get_options() -> dict:
    return {
        "sizes": [
            {**s, "per_page": labels_per_page(k)} for k, s in LABEL_SIZES.items()
        ],
        "themes": list(THEMES.values()),
        # Only advertise icons the renderer can actually draw
        "icons": [i for k, i in ICONS.items() if k in DRAWABLE_ICONS],
        "rating": {
            "kinds": ["none", "stars", "points"],
            "stars_max": STARS_MAX,
            "points_min": POINTS_MIN,
            "points_max": POINTS_MAX,
        },
        "defaults": {"size": DEFAULT_SIZE, "theme": DEFAULT_THEME, "icon": DEFAULT_ICON},
        "blank": blank_label(),
    }


@router.get("/products", response_model=list[ProductSuggestion],
            summary="Your best sellers with their latest price, for one-click prefill")
async def get_products(
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
):
    return await svc.product_suggestions(current_store.id, db)


@router.post("/preview", summary="Live PNG preview of a label (not saved)",
             response_class=Response)
async def preview(
    body: LabelIn,
    current_store: Annotated[Store, Depends(get_current_store)],
) -> Response:
    """
    The editor previews by asking the SERVER to draw the label, so what the owner
    sees is pixel-identical to what prints — no second layout engine in the
    browser to drift out of sync.
    """
    png = await render_label(body.spec)
    return Response(content=png, media_type="image/png",
                    headers={"Cache-Control": "no-store"})


@router.get("/labels", response_model=list[LabelOut], summary="Your saved labels")
async def list_labels(
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
):
    return await svc.list_labels(current_store.id, db)


@router.post("/labels", response_model=LabelOut, status_code=status.HTTP_201_CREATED,
             summary="Create a label")
async def create_label(
    body: LabelIn,
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
):
    return await svc.create_label(current_store.id, db, body.spec)


@router.get("/labels/{label_id}", response_model=LabelOut, summary="Reopen a label")
async def get_label(
    label_id: uuid.UUID,
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
):
    try:
        return await svc.get_label(label_id, current_store.id, db)
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))


@router.put("/labels/{label_id}", response_model=LabelOut, summary="Save edits")
async def save_label(
    label_id: uuid.UUID,
    body: LabelIn,
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
):
    try:
        return await svc.save_label(label_id, current_store.id, body.spec, db)
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/labels/{label_id}/export", response_model=LabelOut,
             summary="Render the label to a stored PNG")
async def export_label(
    label_id: uuid.UUID,
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
):
    try:
        return await svc.export_label(label_id, current_store.id, db)
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/labels/{label_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Delete a label")
async def delete_label(
    label_id: uuid.UUID,
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await svc.delete_label(label_id, current_store.id, db)
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/sheet", summary="Printable US Letter PDF of the selected labels",
             response_class=Response)
async def sheet(
    body: SheetIn,
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        pdf = await svc.sheet_for_labels(body.label_ids, current_store.id, db, body.size)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    return Response(
        content=pdf, media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="liquoriq-shelf-labels.pdf"'},
    )
