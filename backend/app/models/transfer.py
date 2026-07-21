"""
models/transfer.py — Exchange partners + inter-store transfer ledger (Phase 14)

REAL WORKFLOW (pilot owner): a store exchanges stock with OTHER liquor stores —
some their own, some entirely independent (Sherry's, World Wine, …) that may
never use LiquorIQ. So the ledger is kept per PARTNER, from the current
store's point of view:

  TransferPartner  = a store we exchange with, added by name. Security:
                     adding a partner that uses LiquorIQ requires entering
                     THEIR store's exchange_code (which links the accounts);
                     off-app partners get a generated partner_code that can
                     link them later if they ever join.
  Transfer         = one exchange event with a partner, direction is from
                     OUR store's view: "outgoing" (we sent) / "incoming".
  TransferItem     = line items at WHOLESALE cost.
  SettlementPayment= money paid between us and the partner; payer is
                     "me" (our store paid) or "partner".

Balances/monthly statements are DERIVED from raw records (never stored) —
corrections and undos self-heal, carry-forward falls out of the math.
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

    # The store whose partner list this is (each of an owner's stores keeps its own)
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # The security key for this relationship. Either the partner store's
    # exchange_code (when linked) or a generated code we hand to them.
    partner_code: Mapped[str] = mapped_column(String(16), nullable=False)
    # Set when the partner is a LiquorIQ store (added via their exchange_code)
    linked_store_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="SET NULL"), nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )

    def __repr__(self) -> str:
        return f"<TransferPartner id={self.id} name={self.name}>"


class Transfer(Base):
    __tablename__ = "transfers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    partner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transfer_partners.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    # From OUR store's point of view
    direction: Mapped[str] = mapped_column(
        String(10), nullable=False,
        comment="outgoing = we sent stock to the partner; incoming = we received",
    )
    transfer_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )

    items: Mapped[list["TransferItem"]] = relationship(
        "TransferItem", back_populates="transfer",
        cascade="all, delete-orphan", lazy="selectin",
    )
    partner: Mapped["TransferPartner"] = relationship("TransferPartner", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Transfer id={self.id} {self.direction} partner={self.partner_id} {self.transfer_date}>"


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

    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    partner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transfer_partners.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    # "me" = our store paid the partner; "partner" = they paid us
    payer: Mapped[str] = mapped_column(String(10), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    paid_on: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )

    def __repr__(self) -> str:
        return f"<SettlementPayment {self.payer} ${self.amount} partner={self.partner_id}>"
