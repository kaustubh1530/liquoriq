"""
models/campaign_workspace.py — PHASE 23.7: a campaign as a project, not a page.

WHAT THIS TABLE IS FOR

Until now a "campaign" was a strategy row plus whatever assets happened to
reference it. Nothing recorded that the owner had started work, got as far as
the ad, and meant to come back. Close the tab and the only record of intent was
in his head.

This is the row that makes a campaign a PROJECT: it survives the tab closing,
it knows what stage the work reached, and it holds the schedule the owner
chose before anything is actually sent.

WHAT IT DELIBERATELY DOES NOT HOLD

Asset content. The ad lives in ad_creatives, the labels in label_designs, the
sends in campaigns. Copying any of that here would create a second source of
truth for the same thing, and the two would drift — the lesson from Phase 22
that keeps recurring. Progress is COMPUTED by looking at the real assets, not
stored as a set of flags someone has to remember to update.

SCHEDULING IS PREPARATION, NOT EXECUTION. Storing a `scheduled_for` does not
send anything. A worker that reads these rows is a later phase; recording the
owner's intent is this one.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# The lifecycle. Deliberately short — a status per asset would duplicate what
# the assets already know.
STATUSES = ("draft", "ready", "scheduled", "launched", "completed", "cancelled")

# When the owner wants it to go out. Stored as an intent plus a resolved
# timestamp, so "Friday evening" survives as a choice AND as a datetime.
SCHEDULE_PRESETS = (
    "immediately", "tomorrow", "friday_evening", "saturday_morning",
    "holiday_morning", "custom",
)


class CampaignWorkspace(Base):
    """One campaign being executed, from strategy to ROI."""

    __tablename__ = "campaign_workspaces"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # The strategy IS the campaign's brief. One workspace per strategy.
    strategy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_strategy_reports.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")

    # Preparation, not execution. Nothing reads these to send anything yet.
    schedule_preset: Mapped[str | None] = mapped_column(String(30), nullable=True)
    scheduled_for: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    schedule_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Owner edits to generated copy, keyed by channel. Kept here rather than
    # overwriting the strategy, so the original AI output stays auditable and
    # a bad edit can be reverted by clearing one key.
    copy_overrides: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
        nullable=False,
    )
    launched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<CampaignWorkspace {self.strategy_id} ({self.status})>"
