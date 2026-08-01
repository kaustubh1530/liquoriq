"""
models/label_design.py — MODULE 2: LABEL STUDIO (persistence)

One saved SHELF LABEL: the little card a store clips to the shelf edge. It is
fully decoupled from AdCreative — creative_id is optional provenance only, and
is SET NULL on delete so a label outlives any ad it was inspired by.

design_json holds the label spec (validated by services/shelf_label.py):
  {
    "size": "medium", "theme": "bold", "icon": "bottle",
    "product_name": "Buffalo Trace", "price": "$27.99", "was_price": "$32.99",
    "tagline": "STAFF PICK", "details": ["90 proof", "750 ML"],
    "rating": {"kind": "stars", "value": 4.5, "source": "Vivino"},
    "show_border": true
  }

final_image_url is the rendered PNG, written on export.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class LabelDesign(Base):
    """One editable label overlay document, owned by a store."""

    __tablename__ = "label_designs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # Optional provenance: which generated ad this design started from.
    # SET NULL (not CASCADE) — the design outlives the creative it came from.
    creative_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ad_creatives.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False, default="Untitled design")
    # Optional: only set for overlay-style designs. Shelf labels draw their own
    # clean background, so they leave this NULL.
    base_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Flattened result — only written on export; NULL until then
    final_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    design_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<LabelDesign {self.id} name={self.name!r} labels={len(self.design_json.get('labels', []))}>"
