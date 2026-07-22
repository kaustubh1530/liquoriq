"""
models/transfer.py — Shared inter-store exchange ledger (Phase 14, shared model)

Real workflow (~$80-90k/month per store): two LiquorIQ stores exchange stock.
The ledger is SHARED — both stores see the same records — but every record is
audited: who added it, and (on undo) who removed it.

How linking works (both stores must be on LiquorIQ, code mandatory):
  - Each Store has a unique exchange_code.
  - Classy adds "Sherry's" by entering Sherry's code → a TransferPartner row
    (Classy → Sherry's, linked_store_id set). Classy can now record exchanges.
  - Sherry's sees the SAME history only after adding Classy's code (their own
    TransferPartner row Sherry's → Classy).
  - Transfers/payments are keyed by the real store PAIR (from_store_id,
    to_store_id), so both members query the same rows.

Audit + undo:
  - created_by_label / created_by_store_id record who entered a row.
  - Undo is a SOFT delete: is_deleted + deleted_by_label + deleted_at. The row
    stays for the audit trail (shown struck-through) and drops out of balances.
  - Derive-don't-snapshot: balances recompute from non-deleted rows, so undo
    self-heals every number.
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TransferPartner(Base):
    __tablename__ = "transfer_partners"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # The store that owns this partner entry
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # The real LiquorIQ store on the other side (MANDATORY — resolved from code)
    linked_store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False,
    )
    # Display name (defaults to the linked store's name)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )

    def __repr__(self) -> str:
        return f"<TransferPartner {self.store_id}→{self.linked_store_id} {self.name}>"


class Transfer(Base):
    __tablename__ = "transfers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # The real stores on each side (both LiquorIQ stores). Either sees this row.
    from_store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    to_store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    transfer_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Audit: who added this ─────────────────────────────────────────────────
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    created_by_store_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="SET NULL"), nullable=True,
    )
    created_by_label: Mapped[str | None] = mapped_column(
        String(320), nullable=True, comment='e.g. "Jane Doe · Classy Corks"',
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )

    # ── Soft delete (undo) + audit of who removed it ─────────────────────────
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_by_label: Mapped[str | None] = mapped_column(String(320), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[list["TransferItem"]] = relationship(
        "TransferItem", back_populates="transfer",
        cascade="all, delete-orphan", lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Transfer id={self.id} {self.from_store_id}→{self.to_store_id} {self.transfer_date}>"


class TransferItem(Base):
    __tablename__ = "transfer_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transfer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transfers.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    product_name: Mapped[str] = mapped_column(String(500), nullable=False)
    sku: Mapped[str | None] = mapped_column(String(100), nullable=True)
    quantity: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)
    unit_cost: Mapped[float] = mapped_column(
        Numeric(12, 2), nullable=False,
        comment="WHOLESALE cost per unit — exchanges settle at cost",
    )
    line_total: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)

    transfer: Mapped["Transfer"] = relationship("Transfer", back_populates="items")


class SettlementPayment(Base):
    __tablename__ = "settlement_payments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # payer paid payee — both real stores in the pair
    from_store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    to_store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    paid_on: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    created_by_store_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="SET NULL"), nullable=True,
    )
    created_by_label: Mapped[str | None] = mapped_column(String(320), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_by_label: Mapped[str | None] = mapped_column(String(320), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<SettlementPayment {self.from_store_id}→{self.to_store_id} ${self.amount}>"
