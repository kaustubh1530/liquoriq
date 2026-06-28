"""
models/ai_strategy_report.py — AIStrategyReport ORM model

Every AI-generated promotion strategy is saved here.
This gives the store owner a history of all past strategies and lets us
show "last 5 campaigns" in the dashboard without re-calling OpenAI.

Design notes:
  - All AI output fields are Text (not String) — AI copy can be long
  - products_analyzed and products_to_promote are JSON — list of dicts
  - model_used records which OpenAI model generated this (for future auditing)
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AIStrategyReport(Base):
    __tablename__ = "ai_strategy_reports"

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

    # ── Input context sent to OpenAI ──────────────────────────────────────────
    store_name: Mapped[str] = mapped_column(String(255), nullable=False)
    products_analyzed: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        comment="The slow-moving products data sent to the AI",
    )

    # ── AI-generated output ───────────────────────────────────────────────────
    strategy_title: Mapped[str] = mapped_column(String(500), nullable=False)
    products_to_promote: Mapped[list] = mapped_column(JSON, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    target_customer_segment: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_offer: Mapped[str] = mapped_column(Text, nullable=False)
    sms_copy: Mapped[str] = mapped_column(Text, nullable=False)
    email_subject: Mapped[str] = mapped_column(String(500), nullable=False)
    email_body: Mapped[str] = mapped_column(Text, nullable=False)
    social_caption: Mapped[str] = mapped_column(Text, nullable=False)
    expected_impact: Mapped[str] = mapped_column(Text, nullable=False)

    # ── Meta ──────────────────────────────────────────────────────────────────
    model_used: Mapped[str] = mapped_column(String(50), nullable=False, default="gpt-4o")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    store: Mapped["Store"] = relationship("Store")  # noqa: F821

    def __repr__(self) -> str:
        return f"<AIStrategyReport id={self.id} title={self.strategy_title}>"