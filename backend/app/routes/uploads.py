"""
routes/uploads.py — Report upload endpoints

POST /uploads/report   — upload a CSV/Excel report (POS, Uber Eats, etc.)
GET  /uploads          — list all uploads for the logged-in user's store
GET  /uploads/{id}     — get details of one upload

File handling strategy:
  - Validate extension (.csv, .xlsx, .xls) and size before touching disk
  - Save with a randomized filename to avoid collisions and path traversal
  - Store files under uploads/{store_id}/ so each store's data is isolated
  - Record everything in the database — the file on disk is just storage,
    the DB row is the source of truth for status and metadata

Phase 5 will read `file_path` from these records and run them through a
source-specific parser (AdvEntPOS, generic CSV, etc.).
"""

import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.store import Store
from app.models.uploaded_report import ReportSource, ReportStatus, UploadedReport
from app.routes.stores import get_current_store
from app.schemas.upload import UploadResponse

router = APIRouter()
settings = get_settings()

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


@router.post(
    "/report",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a CSV/Excel report (POS, website, Uber Eats, DoorDash, etc.)",
)
async def upload_report(
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
    file: UploadFile = File(..., description="The CSV or Excel report file"),
    source: ReportSource = ReportSource.OTHER,
) -> UploadedReport:
    # ── 1. Validate file extension ───────────────────────────────────────────
    original_name = file.filename or "unnamed"
    extension = Path(original_name).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported file type '{extension}'. "
                f"Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            ),
        )

    # ── 2. Read file into memory and validate size ───────────────────────────
    # For MVP we read fully into memory — fine for report-sized files.
    # If we ever need multi-GB files, switch to chunked streaming to disk.
    contents = await file.read()
    file_size = len(contents)
    max_bytes = settings.max_upload_size_mb * 1024 * 1024

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    if file_size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {settings.max_upload_size_mb}MB limit.",
        )

    # ── 3. Build a safe, collision-proof storage path ────────────────────────
    # Pattern: uploads/{store_id}/{uuid}{extension}
    # We never trust the original filename for the path — only for display.
    stored_filename = f"{uuid.uuid4()}{extension}"
    store_dir = Path(settings.upload_dir) / str(current_store.id)
    store_dir.mkdir(parents=True, exist_ok=True)
    file_path = store_dir / stored_filename

    with open(file_path, "wb") as f:
        f.write(contents)

    # ── 4. Record the upload in the database ─────────────────────────────────
    new_upload = UploadedReport(
        store_id=current_store.id,
        source=source,
        original_filename=original_name,
        stored_filename=stored_filename,
        file_path=str(file_path),
        file_size_bytes=file_size,
        status=ReportStatus.PENDING,  # Phase 5 will pick this up for parsing
    )
    db.add(new_upload)
    await db.flush()
    await db.refresh(new_upload)

    return new_upload


@router.get(
    "",
    response_model=list[UploadResponse],
    summary="List all uploads for the logged-in user's store",
)
async def list_uploads(
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> list[UploadedReport]:
    result = await db.execute(
        select(UploadedReport)
        .where(UploadedReport.store_id == current_store.id)
        .order_by(UploadedReport.uploaded_at.desc())
    )
    return list(result.scalars().all())


@router.get(
    "/{upload_id}",
    response_model=UploadResponse,
    summary="Get details of a single upload",
)
async def get_upload(
    upload_id: uuid.UUID,
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> UploadedReport:
    result = await db.execute(
        select(UploadedReport).where(
            UploadedReport.id == upload_id,
            UploadedReport.store_id == current_store.id,  # ownership check
        )
    )
    upload = result.scalar_one_or_none()

    if upload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload not found.",
        )

    return upload