"""
models/product_category.py — PHASE 22: Category Intelligence cache

Tiers 1 and 2 of the category cascade live here.

The POS export has no category column, so every product's category is RESOLVED
(brand dictionary → keyword dictionary → AI → owner correction). Storing the
result keyed by SKU means:
  · the next upload skips straight to the cache (tier 2) — faster and cheaper
  · an owner correction (source="manual") is permanent and beats every
    automatic tier forever
  · SKU is the key, not the product name, because names get re-typed between
    exports while the UPC stays put
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ProductCategory(Base):
    """One resolved category for one product, scoped to a store."""

    __tablename__ = "product_categories"
    __table_args__ = (
        UniqueConstraint("store_id", "product_key", name="uq_product_category_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    # SKU/UPC where present, else the upper-cased product name.
    product_key: Mapped[str] = mapped_column(String(200), nullable=False)
    product_name: Mapped[str] = mapped_column(String(500), nullable=False, default="")

    category: Mapped[str] = mapped_column(String(40), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(80), nullable=True)

    # Which tier produced this: manual | brand | dictionary | ai
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="dictionary")
    confidence: Mapped[str] = mapped_column(String(10), nullable=False, default="medium")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ProductCategory {self.product_key} → {self.category} ({self.source})>"
