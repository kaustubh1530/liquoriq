"""phase 23: advisor conversations and messages

Revision ID: c4e8b2f713a9
Revises: b8f4c2a91d7e
Create Date: 2026-08-04

The advisor has to remember the thread: "I'm thinking about Labor Day" followed
by "what should I promote?" is one conversation, not two questions. Persisted
server-side so closing the tab doesn't erase it, and because tools_used is an
audit trail — a client-held history could be edited, and history is an input to
a system that spends money on API calls.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'c4e8b2f713a9'
down_revision: Union[str, None] = 'b8f4c2a91d7e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'advisor_conversations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('store_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False,
                  server_default='New conversation'),
        sa.Column('message_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_advisor_conversations_store_id',
                    'advisor_conversations', ['store_id'])

    op.create_table(
        'advisor_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('tools_used', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['advisor_conversations.id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_advisor_messages_conversation_id',
                    'advisor_messages', ['conversation_id'])


def downgrade() -> None:
    op.drop_index('ix_advisor_messages_conversation_id', table_name='advisor_messages')
    op.drop_table('advisor_messages')
    op.drop_index('ix_advisor_conversations_store_id', table_name='advisor_conversations')
    op.drop_table('advisor_conversations')
