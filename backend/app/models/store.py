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
    # Phase 14: unique=True removed — one owner can now own MANY stores
    # (the pilot owner runs 4). Migration f3d82c1a9b47 drops the DB constraint.
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
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

    # ── Exchange code (Phase 14 partners) ────────────────────────────────────
    # The security key another store must present to add THIS store as an
    # exchange partner. Shown in the Transfers tab; shared verbally/on paper.
    exchange_code: Mapped[str | None] = mapped_column(
        String(16),
        unique=True,
        nullable=True,
        default=lambda: uuid.uuid4().hex[:8].upper(),
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
    # foreign_keys is explicit because users↔stores now have circular FKs
    # (Store.owner_id → users.id AND users.store_id → stores.id for staff).
    owner: Mapped["User"] = relationship(  # noqa: F821
        "User",
        back_populates="stores",
        foreign_keys=[owner_id],
    )

    def __repr__(self) -> str:
        return f"<Store id={self.id} name={self.name}>"