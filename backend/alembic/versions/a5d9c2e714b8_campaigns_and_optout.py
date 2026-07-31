"""campaigns, message logs, and customer opt-out suppression

Revision ID: a5d9c2e714b8
Revises: f1a3c8e290d4
Create Date: 2026-07-25

Phase 21: SMS/email distribution to opted-in customers.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a5d9c2e714b8'
down_revision: Union[str, None] = 'f1a3c8e290d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Suppression list on customers
    op.add_column('customers', sa.Column('sms_opted_out', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('customers', sa.Column('email_opted_out', sa.Boolean(), nullable=False, server_default=sa.false()))

    op.create_table('campaigns',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('store_id', sa.UUID(), nullable=False),
        sa.Column('strategy_id', sa.UUID(), nullable=True),
        sa.Column('channel', sa.String(length=10), nullable=False),
        sa.Column('target_segment', sa.String(length=30), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('recipients_total', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('sent_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('skipped_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_by_user_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['strategy_id'], ['ai_strategy_reports.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_campaigns_store_id'), 'campaigns', ['store_id'])

    op.create_table('message_logs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('store_id', sa.UUID(), nullable=False),
        sa.Column('campaign_id', sa.UUID(), nullable=False),
        sa.Column('customer_id', sa.UUID(), nullable=True),
        sa.Column('channel', sa.String(length=10), nullable=False),
        sa.Column('to_address', sa.String(length=320), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_message_logs_store_id'), 'message_logs', ['store_id'])
    op.create_index(op.f('ix_message_logs_campaign_id'), 'message_logs', ['campaign_id'])


def downgrade() -> None:
    op.drop_table('message_logs')
    op.drop_table('campaigns')
    op.drop_column('customers', 'email_opted_out')
    op.drop_column('customers', 'sms_opted_out')
