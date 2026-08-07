"""phase 23.7: campaign workspaces

Revision ID: d5a1f39c8b02
Revises: c4e8b2f713a9
Create Date: 2026-08-04

Makes a campaign a PROJECT rather than a page. Records that the owner started
work, and the schedule he chose — nothing else records intent, and closing the
tab used to erase it.

Deliberately holds no asset content: the ad lives in ad_creatives, labels in
label_designs, sends in campaigns. Progress is COMPUTED from those, never
stored as flags, because flags drift and a progress bar that disagrees with the
owner's own assets is worse than none.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'd5a1f39c8b02'
down_revision: Union[str, None] = 'c4e8b2f713a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'campaign_workspaces',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('store_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('strategy_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False,
                  server_default='draft'),
        sa.Column('schedule_preset', sa.String(length=30), nullable=True),
        sa.Column('scheduled_for', sa.DateTime(timezone=True), nullable=True),
        sa.Column('schedule_note', sa.Text(), nullable=True),
        sa.Column('copy_overrides', postgresql.JSONB(astext_type=sa.Text()),
                  nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('launched_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['strategy_id'], ['ai_strategy_reports.id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        # One workspace per strategy: the strategy IS the campaign's brief.
        sa.UniqueConstraint('strategy_id', name='uq_workspace_strategy'),
    )
    op.create_index('ix_campaign_workspaces_store_id',
                    'campaign_workspaces', ['store_id'])


def downgrade() -> None:
    op.drop_index('ix_campaign_workspaces_store_id',
                  table_name='campaign_workspaces')
    op.drop_table('campaign_workspaces')
