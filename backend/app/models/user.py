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

from sqlalchemy import Boolean, DateTime, ForeignKey, String
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

    # ── Role & store assignment (Phase 14: multi-store + staff) ──────────────
    # "owner": owns stores (via Store.owner_id), switches between them freely.
    # "staff": created by an owner, permanently pinned to ONE store (store_id).
    role: Mapped[str] = mapped_column(String(20), default="owner", nullable=False)
    store_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE", use_alter=True, name="fk_users_store_id"),
        nullable=True,
        comment="Staff only: the store this account is pinned to",
    )

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
    # Phase 14: one OWNER → many stores. (Circular FKs users↔stores mean every
    # relationship must name its foreign_keys explicitly.)
    stores: Mapped[list["Store"]] = relationship(  # noqa: F821
        "Store",
        back_populates="owner",
        foreign_keys="Store.owner_id",
        lazy="selectin",
        order_by="Store.created_at",
    )
    # Staff only: the single store this account is pinned to.
    assigned_store: Mapped["Store | None"] = relationship(  # noqa: F821
        "Store",
        foreign_keys=[store_id],
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"