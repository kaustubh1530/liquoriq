"""
models/ad_creative.py — AdCreative ORM model

One row = one complete ad-creative package generated from a strategy:
a DALL-E 3 image plus platform-specific copy for Instagram, Facebook,
Uber Eats, DoorDash, and the store's website banner.

Design notes:
  - strategy_id FK → ai_strategy_reports: a creative always belongs to a
    strategy. NOT unique — regenerating creates a new row (history kept),
    and GET /creative/{strategy_id} returns the newest one.
  - image_url stores a relative path ("/static/creatives/<file>.png") so it
    works in dev and prod without hardcoding a host.
  - image_prompt is saved for auditing/regeneration — you can see exactly
    what DALL-E was asked to draw.
  - Copy fields are Text — platform copy can be long (especially Facebook).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AdCreative(Base):
    __tablename__ = "ad_creatives"

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
    strategy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_strategy_reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Generated image ───────────────────────────────────────────────────────
    image_prompt: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="The exact prompt sent to DALL-E 3",
    )
    image_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Relative URL, e.g. /static/creatives/<uuid>.png",
    )

    # ── Composed final ad (Phase 11 — price overlay) ──────────────────────────
    # The original AI image stays untouched in image_url. When the owner sets
    # prices and clicks Compose, Pillow stamps names+prices onto a copy and the
    # result lands here. Nullable: a creative may never be composed.
    final_image_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Composed ad with deterministic price overlay",
    )
    price_items: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment='[{"product_name": str, "price": float}] used in the overlay',
    )

    # ── Platform-specific copy ────────────────────────────────────────────────
    instagram_caption: Mapped[str] = mapped_column(Text, nullable=False)
    facebook_post: Mapped[str] = mapped_column(Text, nullable=False)
    ubereats_description: Mapped[str] = mapped_column(Text, nullable=False)
    doordash_description: Mapped[str] = mapped_column(Text, nullable=False)
    website_banner_headline: Mapped[str] = mapped_column(String(200), nullable=False)
    website_banner_text: Mapped[str] = mapped_column(Text, nullable=False)

    # ── Meta ──────────────────────────────────────────────────────────────────
    model_used: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="gpt-4o + dall-e-3",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    strategy: Mapped["AIStrategyReport"] = relationship("AIStrategyReport")  # noqa: F821

    def __repr__(self) -> str:
        return f"<AdCreative id={self.id} strategy_id={self.strategy_id}>"
