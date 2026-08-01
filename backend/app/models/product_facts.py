"""
models/product_facts.py — Reusable, owner-confirmed product facts (Professional
Ad Upgrade, Part 2)

Owner enters or confirms real product details ONCE per product (category-specific:
wine vintage/region, whiskey proof/age, tequila NOM/agave, etc.). Stored keyed to
(store, product) and reused for every future ad — so the AI uses ONLY confirmed
facts and never hallucinates a proof, award, or origin.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ProductFacts(Base):
    __tablename__ = "product_facts"
    __table_args__ = (
        UniqueConstraint("store_id", "product_key", name="uq_product_facts_store_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    product_key: Mapped[str] = mapped_column(String(500), nullable=False, index=True)  # lowercased name
    product_name: Mapped[str] = mapped_column(String(500), nullable=False)             # display
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Free-form confirmed facts (category-specific keys). Owner-controlled.
    facts: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
