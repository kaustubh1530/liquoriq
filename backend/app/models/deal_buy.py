"""
models/deal_buy.py — Supplier closeout / deal buys (Phase 15)

The real profit lever for a liquor store: distributors dump inventory cheap
(wine at $2-3, liquor at ~50% off cost). Those are high-margin promo weapons —
but the app can't know about them unless the owner records them. This table
captures deal buys so the AI builds aggressive, still-profitable campaigns
around moving that stock.
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DealBuy(Base):
    __tablename__ = "deal_buys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    product_name: Mapped[str] = mapped_column(String(500), nullable=False)
    category: Mapped[str | None] = mapped_column(String(200), nullable=True)

    cost_price: Mapped[float] = mapped_column(
        Numeric(12, 2), nullable=False, comment="What the store paid per unit on this deal")
    normal_price: Mapped[float | None] = mapped_column(
        Numeric(12, 2), nullable=True, comment="Usual retail price per unit")
    quantity: Mapped[float | None] = mapped_column(
        Numeric(12, 2), nullable=True, comment="Units bought on the deal")

    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )

    def __repr__(self) -> str:
        return f"<DealBuy id={self.id} {self.product_name} @ {self.cost_price}>"
