"""
models/customer.py — Customers + purchase history (Phase 19)

Customer ingestion + RFM segmentation. Each store owns its own customer list
(strict store isolation via store_id). We store identity, marketing consent
(prepared for future Twilio SMS / email — no messages sent yet), and
denormalized RFM aggregates (last purchase, count, total spent) so segmentation
is fast. CustomerPurchase keeps transaction-level history when the POS report
provides it.

Dedup: a customer is unique per store by `dedup_key` (email → phone digits →
name, lowercased). Re-uploading a report is idempotent — the customer is
updated, not duplicated.
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("store_id", "dedup_key", name="uq_customer_store_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # email → 'p:'+digits → 'n:'+name (lowercased). Identity + idempotency key.
    dedup_key: Mapped[str] = mapped_column(String(320), nullable=False, index=True)

    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # ── RFM aggregates (snapshot from the latest report; derived, self-correcting)
    total_spent: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    purchase_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    first_purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # ── Marketing consent (prepared for Twilio/email — NOT sending yet) ────────
    sms_opt_in: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_opt_in: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Suppression list (Phase 21): once opted OUT, never messaged again — survives
    # re-uploads (ingestion never clears these). Compliance requirement.
    sms_opted_out: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_opted_out: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    purchases: Mapped[list["CustomerPurchase"]] = relationship(
        "CustomerPurchase", back_populates="customer", cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Customer {self.dedup_key} store={self.store_id}>"


class CustomerPurchase(Base):
    __tablename__ = "customer_purchases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    product_name: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )

    customer: Mapped["Customer"] = relationship("Customer", back_populates="purchases")

    def __repr__(self) -> str:
        return f"<CustomerPurchase cust={self.customer_id} ${self.amount}>"
