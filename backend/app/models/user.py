"""
models/user.py — User ORM model

Represents a store owner who has an account in LiquorIQ.
One user can own one store (for MVP). Multi-store support comes later.

Why UUID for primary key instead of integer?
  - UUIDs don't expose record counts (attacker can't guess IDs)
  - Safe to generate on the client or server side
  - Industry standard for SaaS user IDs
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    # ── Primary key ───────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # ── Identity ──────────────────────────────────────────────────────────────
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,   # fast email lookups during login
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # ── Auth ──────────────────────────────────────────────────────────────────
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

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
    # One user → one store (MVP). back_populates wires the reverse side.
    store: Mapped["Store"] = relationship(  # noqa: F821
        "Store",
        back_populates="owner",
        uselist=False,   # uselist=False = one-to-one
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"