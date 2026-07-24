"""
models/product_photo.py — Reusable product photo library (Phase 16)

"Upload once, reuse forever." The first time an owner attaches a real bottle
photo for a product, we save it here keyed to (store, product name). Every
future ad for that product auto-uses it — so the owner never re-uploads, and
coverage of their catalog compounds as they make ads.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ProductPhoto(Base):
    __tablename__ = "product_photos"
    __table_args__ = (
        UniqueConstraint("store_id", "product_key", name="uq_product_photo_store_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # Lowercased/trimmed product name — the lookup key (names come from strategies)
    product_key: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    product_name: Mapped[str] = mapped_column(String(500), nullable=False)  # display
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<ProductPhoto store={self.store_id} {self.product_name}>"
