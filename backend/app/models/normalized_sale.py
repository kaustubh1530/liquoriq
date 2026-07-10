"""
models/normalized_sale.py — NormalizedSale ORM model

This is LiquorIQ's core data table. Every uploaded report — regardless of
whether it came from AdvEntPOS, Uber Eats, DoorDash, or any other platform —
gets normalized into rows in this table.

Why normalization?
  Different platforms use completely different column names for the same data:
    DoorDash  → "Item Name",  "Order Total", "Order Date"
    Uber Eats → "Product",    "Net Price",   "Delivered At"
    AdvEntPOS → "Dept",       "Net Sales",   "Date"
  LiquorIQ maps all of them to one consistent schema so analytics can run
  the same SQL queries regardless of source.

Key design decisions:
  - Numeric(12, 2) for money — never use Float for financial data
  - raw_row stores the original CSV row as JSON — useful for debugging bad data
  - All customer fields are nullable — delivery apps rarely include PII
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, JSON, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class NormalizedSale(Base):
    __tablename__ = "normalized_sales"

    # ── Primary key ───────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # ── Traceability — which store and which upload produced this row ──────────
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    upload_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("uploaded_reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Core sales data ───────────────────────────────────────────────────────
    sale_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    product_name: Mapped[str] = mapped_column(String(500), nullable=False)
    sku: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    category: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)

    # ── Quantities and pricing (Numeric for financial accuracy) ───────────────
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    # Phase 13: AdvEntPOS summary reports include current inventory per product.
    # Snapshot as of the report period — fuels reorder/dead-stock intelligence.
    stock_on_hand: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)

    # ── Channel — which platform this sale came from ──────────────────────────
    channel: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pos",
        index=True,
        comment="pos | website | uber_eats | doordash | other",
    )

    # ── Customer info (nullable — not all sources provide this) ───────────────
    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # ── Original row as JSON — for debugging bad parses ───────────────────────
    raw_row: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # ── Timestamp ─────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    store: Mapped["Store"] = relationship("Store")          # noqa: F821
    upload: Mapped["UploadedReport"] = relationship("UploadedReport")  # noqa: F821

    def __repr__(self) -> str:
        return f"<NormalizedSale id={self.id} product={self.product_name} date={self.sale_date}>"