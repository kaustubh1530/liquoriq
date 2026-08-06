"""
models/advisor_conversation.py — PHASE 23: the advisor's memory.

WHY THIS IS PERSISTED RATHER THAN HELD IN THE BROWSER

The owner says "I'm thinking about Labor Day", then two minutes later "what
should I promote?". The second question is meaningless without the first, and
an advisor that has to be re-briefed every message is not an advisor.

Server-side because:
  · he closes the tab, comes back after serving a customer, and expects the
    thread to still be there
  · the tools each turn called are part of the record — that is the audit
    trail behind "why I recommended this"
  · a browser-held history can be edited by the client, and history is an
    input to a system that spends money

Messages are append-only. Nothing here rewrites what the advisor said.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AdvisorConversation(Base):
    """One thread between an owner and the advisor."""

    __tablename__ = "advisor_conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # Taken from the first question, so the history list is scannable without
    # opening each thread.
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="New conversation")
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
        nullable=False,
    )

    messages: Mapped[list["AdvisorMessage"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan",
        order_by="AdvisorMessage.created_at",
    )


class AdvisorMessage(Base):
    """One turn. Append-only."""

    __tablename__ = "advisor_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("advisor_conversations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    role: Mapped[str] = mapped_column(String(20), nullable=False)   # user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # WHICH TOOLS ACTUALLY RAN for this answer. Recorded rather than asked for:
    # a model's claim about its own sources is not evidence, and this is what
    # the UI shows under "business context used".
    tools_used: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    conversation: Mapped[AdvisorConversation] = relationship(back_populates="messages")
