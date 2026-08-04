"""
models/uploaded_report.py — UploadedReport ORM model

Tracks every file a store owner uploads: where it came from (source),
where it's stored on disk, and its processing status.

This table is the audit trail for Phase 5 (parsing). Once we build the
parser, it will read `file_path`, transform the rows into `normalized_sales`
records, then flip `status` to "completed" or "failed".

Status lifecycle:
  pending → processing → completed
                       └→ failed (with error_message set)
"""

import enum
import uuid
from datetime import date as dt_date, datetime, timezone

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ReportSource(str, enum.Enum):
    """Where the uploaded report came from. Drives which parser Phase 5 picks."""
    POS = "pos"
    WEBSITE = "website"
    UBER_EATS = "uber_eats"
    DOORDASH = "doordash"
    OTHER = "other"


class ReportStatus(str, enum.Enum):
    """Processing lifecycle of an uploaded report."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class UploadedReport(Base):
    __tablename__ = "uploaded_reports"

    # ── Primary key ───────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # ── Ownership ─────────────────────────────────────────────────────────────
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Source classification ────────────────────────────────────────────────
    source: Mapped[ReportSource] = mapped_column(
        Enum(ReportSource, name="report_source", native_enum=False, length=20),
        nullable=False,
    )

    # ── File details ──────────────────────────────────────────────────────────
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Randomized filename on disk to avoid collisions",
    )
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # ── Processing status (used heavily in Phase 5) ──────────────────────────
    status: Mapped[ReportStatus] = mapped_column(
        Enum(ReportStatus, name="report_status", native_enum=False, length=20),
        default=ReportStatus.PENDING,
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    rows_processed: Mapped[int | None] = mapped_column(nullable=True)

    # ── Reporting period (Phase 22) ───────────────────────────────────────────
    # The window the file actually covers. Everything velocity-based divides by
    # this instead of assuming ~4.3 weeks: a WEEKLY upload was previously
    # understating velocity 4x, which made every reorder and overstock verdict
    # wrong. period_estimated=True means the file didn't state a period and we
    # fell back to 30 days — the UI says so rather than pretending.
    period_start: Mapped[dt_date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[dt_date | None] = mapped_column(Date, nullable=True)
    period_days: Mapped[int | None] = mapped_column(nullable=True)
    period_estimated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    store: Mapped["Store"] = relationship("Store")  # noqa: F821

    def __repr__(self) -> str:
        return f"<UploadedReport id={self.id} source={self.source} status={self.status}>"