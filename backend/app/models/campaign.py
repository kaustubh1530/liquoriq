"""
models/campaign.py — Campaign delivery + message log (Phase 21)

Records each time an owner SENDS a strategy's copy to customers via SMS or
email. Compliance-first: only opted-in, non-suppressed customers are targeted;
every send is logged per recipient for an audit trail; nothing sends unless the
owner explicitly confirms (and, for SMS, unless Twilio is configured).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    strategy_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_strategy_reports.id", ondelete="SET NULL"), nullable=True,
    )

    channel: Mapped[str] = mapped_column(String(10), nullable=False)   # sms | email
    target_segment: Mapped[str | None] = mapped_column(String(30), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="sent")  # sent|partial|failed|dry_run

    recipients_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sent_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )

    messages: Mapped[list["MessageLog"]] = relationship(
        "MessageLog", back_populates="campaign", cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Campaign {self.channel} store={self.store_id} sent={self.sent_count}>"


class MessageLog(Base):
    __tablename__ = "message_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="SET NULL"), nullable=True,
    )

    channel: Mapped[str] = mapped_column(String(10), nullable=False)
    to_address: Mapped[str | None] = mapped_column(String(320), nullable=True)   # phone/email
    status: Mapped[str] = mapped_column(String(20), nullable=False)              # sent|failed|skipped|dry_run
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False,
    )

    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="messages")
