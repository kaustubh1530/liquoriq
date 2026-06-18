"""
models/store.py — Store ORM model

Represents a physical liquor store owned by a User.
All uploaded reports, analytics, and AI strategies belong to a Store.

Design note:
  We separate User (auth identity) from Store (business entity) intentionally.
  This allows future multi-store support: one user could own multiple stores
  without touching the auth system.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Store(Base):
    __tablename__ = "stores"

    # ── Primary key ───────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # ── Ownership ─────────────────────────────────────────────────────────────
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,    # one store per user (MVP)
        nullable=False,
        index=True,
    )

    # ── Store details ─────────────────────────────────────────────────────────
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(50), nullable=True)
    zip_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # ── POS system info (critical for parser selection in Phase 5) ────────────
    pos_system: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="e.g. AdvEntPOS, Square, Clover — used to select the right parser",
    )

    # ── Status ────────────────────────────────────────────────────────────────
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    owner: Mapped["User"] = relationship(  # noqa: F821
        "User",
        back_populates="store",
    )

    def __repr__(self) -> str:
        return f"<Store id={self.id} name={self.name}>"