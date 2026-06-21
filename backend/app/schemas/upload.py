"""
schemas/upload.py — Pydantic schemas for uploaded reports

UploadResponse — what we return after a file is uploaded or listed.
We never accept a raw "UploadCreate" schema from JSON because the file
itself comes through multipart/form-data, handled directly in the route.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.uploaded_report import ReportSource, ReportStatus


class UploadResponse(BaseModel):
    id: uuid.UUID
    store_id: uuid.UUID
    source: ReportSource
    original_filename: str
    file_size_bytes: int
    status: ReportStatus
    error_message: str | None
    rows_processed: int | None
    uploaded_at: datetime
    processed_at: datetime | None

    model_config = {"from_attributes": True}