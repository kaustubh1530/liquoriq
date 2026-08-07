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
from app.schemas.label_studio import (
    ApplyTemplateIn,
    LabelIn,
    LabelOut,
    ProductSuggestion,
    SheetIn,
    TemplateIn,
)
from app.services import label_design_service as svc
from app.services.shelf_label import (
    ACCENTS,
    ART,
    COLORS,
    CONTENT_FIELDS,
    DEFAULT_ACCENT,
    DEFAULT_FONT,
    DEFAULT_SIZE,
    DEFAULT_ORIENTATION,
    DEFAULT_PAGE,
    DEFAULT_PER_PAGE,
    DEFAULT_STYLE,
    ELEMENT_DEFAULTS,
    ELEMENT_KINDS,
    FONTS,
    LABEL_SIZES,
    PAGE_SIZES,
    ORIENTATIONS,
    SHEET_LAYOUTS,
    STYLE_PRESETS,
    blank_label,
    build_from_style,
    cell_inches,
    sheet_grid,
)
from app.services.shelf_label_renderer import render_label, render_preview

router = APIRouter()


@router.get("/options", summary="Styles, sizes, fonts, art and element defaults")
async def get_options() -> dict:
    return {
        "styles": [{k: v for k, v in s.items() if k != "build"}
                   for s in STYLE_PRESETS.values()],
        "sizes": list(LABEL_SIZES.values()),
        "pages": list(PAGE_SIZES.values()),
        "orientations": list(ORIENTATIONS),
        "sheet_layouts": [
            {"per_page": n,
             "cells": {f"{pg}_{o}": cell_inches(n, pg, o)
                       for pg in PAGE_SIZES for o in ORIENTATIONS},
             "grids": {o: list(sheet_grid(n, o)) for o in ORIENTATIONS}}
            for n in sorted(SHEET_LAYOUTS) if n > 1
        ],
        "fonts": list(FONTS.values()),
        "accents": list(ACCENTS.values()),
        "art": list(ART.values()),
        "element_kinds": list(ELEMENT_KINDS),
        "colors": list(COLORS),
        "element_defaults": ELEMENT_DEFAULTS,
        "content_fields": list(CONTENT_FIELDS),
        "defaults": {"style": DEFAULT_STYLE, "size": DEFAULT_SIZE,
                     "font": DEFAULT_FONT, "accent": DEFAULT_ACCENT,
                     "page": DEFAULT_PAGE, "per_page": DEFAULT_PER_PAGE,
                     "orientation": DEFAULT_ORIENTATION},
        "blank": blank_label(),
    }


@router.post("/from-style", summary="Generate a starting layout from a style + your content")
async def from_style(body: dict) -> dict:
    """
    The "start me off" path: pick a style, type the name and price, and get a
    full set of positioned elements you can then move around freely.
    """
    return {"spec": build_from_style(
        body.get("style") or DEFAULT_STYLE,
        body.get("content") or {},
        body.get("base") or {},
    )}


@router.get("/templates", response_model=list[LabelOut],
            summary="Your saved styles, reusable for any product")
async def list_templates(
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
):
    return await svc.list_templates(current_store.id, db)


@router.post("/templates", response_model=LabelOut, status_code=status.HTTP_201_CREATED,
             summary="Save the current look as a reusable style")
async def create_template(
    body: TemplateIn,
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
):
    return await svc.save_as_template(current_store.id, db, body.spec, body.name)


@router.post("/templates/{template_id}/apply",
             summary="Put your product into a saved style")
async def apply_template(
    template_id: uuid.UUID,
    body: ApplyTemplateIn,
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return {"spec": await svc.apply_template_to(
            template_id, current_store.id, body.spec, db)}
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Delete a saved style")
async def delete_template(
    template_id: uuid.UUID,
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await svc.delete_label(template_id, current_store.id, db)
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/products", response_model=list[ProductSuggestion],
            summary="Your best sellers with their latest price, for one-click prefill")
async def get_products(
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
):
    return await svc.product_suggestions(current_store.id, db)


@router.post("/preview", summary="Live preview + element boxes for the drag editor")
async def preview(
    body: LabelIn,
    current_store: Annotated[Store, Depends(get_current_store)],
) -> dict:
    """
    The SERVER draws the preview, so what the owner sees is exactly what prints —
    no second layout engine in the browser to drift out of sync. It also returns
    each element's box in relative units, which is how the editor places its drag
    handles so they line up perfectly with the drawn label.
    """
    import base64
    png, boxes, (w, h) = await render_preview(body.spec)
    return {
        "image": "data:image/png;base64," + base64.b64encode(png).decode(),
        "boxes": boxes,
        "canvas": {"width": w, "height": h},
    }


@router.get("/labels", response_model=list[LabelOut], summary="Your saved labels")
async def list_labels(
    current_store: Annotated[Store, Depends(get_current_store)],
    strategy_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    """All of this store's labels, or — with `strategy_id` — one campaign's."""
    return await svc.list_labels(current_store.id, db, strategy_id)


@router.post("/labels", response_model=LabelOut, status_code=status.HTTP_201_CREATED,
             summary="Create a label")
async def create_label(
    body: LabelIn,
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
):
    return await svc.create_label(current_store.id, db, body.spec, body.strategy_id)


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


@router.post("/sheet", summary="Printable PDF — N labels per A4/Letter page",
             response_class=Response)
async def sheet(
    body: SheetIn,
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        pdf = await svc.sheet_for_labels(
            body.label_ids, current_store.id, db,
            body.per_page, body.page, body.repeat, body.cut_marks, body.orientation,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    return Response(
        content=pdf, media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="liquoriq-shelf-labels.pdf"'},
    )


@router.post("/sheet-preview", summary="PNG of page 1 — check before spending paper")
async def sheet_preview(
    body: SheetIn,
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    import base64
    try:
        png = await svc.sheet_preview_for_labels(
            body.label_ids, current_store.id, db,
            body.per_page, body.page, body.repeat, body.cut_marks, body.orientation,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    return {"image": "data:image/png;base64," + base64.b64encode(png).decode()}
