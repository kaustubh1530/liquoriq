"""
routes/customers.py — Customer ingestion + RFM segmentation (Phase 19)

POST /customers/upload    — upload a customer report (CSV/Excel)
GET  /customers/segments  — segment summary + marketing recommendations
GET  /customers           — searchable/filterable customer list with RFM

All scoped to the logged-in user's store. No messages are sent (consent fields
are stored for future Twilio SMS / email only).
"""

import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.store import Store
from app.routes.stores import get_current_store
from app.schemas.customer import CustomerListItem, SegmentSummary, UploadResult
from app.services.customer_service import ingest_customers, list_customers, segment_summary
from app.services.parsers.customer_parser import parse_customers

router = APIRouter()


@router.post(
    "/upload",
    response_model=UploadResult,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a customer report (CSV/Excel) and ingest it",
)
async def upload_customers(
    current_store: Annotated[Store, Depends(get_current_store)],
    file: UploadFile = File(..., description="Customer report CSV or Excel"),
    db: AsyncSession = Depends(get_db),
) -> UploadResult:
    raw = await file.read()
    if not raw:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Empty file.")

    suffix = Path(file.filename or "upload.csv").suffix or ".csv"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
        tmp.write(raw)
        tmp.flush()
        try:
            parsed = parse_customers(tmp.name)
        except ValueError as e:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    if not parsed:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="No customers with a name, email, or phone were found.")

    return await ingest_customers(current_store.id, parsed, db)


@router.get(
    "/segments",
    response_model=SegmentSummary,
    summary="RFM segment summary + marketing recommendations",
)
async def customer_segments(
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> SegmentSummary:
    return await segment_summary(current_store.id, db)


@router.get(
    "",
    response_model=list[CustomerListItem],
    summary="Customer list with RFM scores + segment (filter by segment, search by name/email/phone)",
)
async def customers_list(
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
    segment: str | None = Query(default=None),
    search: str | None = Query(default=None),
) -> list[CustomerListItem]:
    return await list_customers(current_store.id, db, segment=segment, search=search)
