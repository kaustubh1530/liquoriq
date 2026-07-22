"""deal buys and strategy 2.0 fields

Revision ID: e7f1a9c3d820
Revises: d4c1e8a7f350
Create Date: 2026-07-20

Phase 15: supplier deal buys + occasion-aware, offline+online strategy fields.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e7f1a9c3d820'
down_revision: Union[str, None] = 'd4c1e8a7f350'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('deal_buys',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('store_id', sa.UUID(), nullable=False),
        sa.Column('product_name', sa.String(length=500), nullable=False),
        sa.Column('category', sa.String(length=200), nullable=True),
        sa.Column('cost_price', sa.Numeric(12, 2), nullable=False,
                  comment='What the store paid per unit on this deal'),
        sa.Column('normal_price', sa.Numeric(12, 2), nullable=True,
                  comment='Usual retail price per unit'),
        sa.Column('quantity', sa.Numeric(12, 2), nullable=True,
                  comment='Units bought on the deal'),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('expires_on', sa.Date(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_deal_buys_store_id'), 'deal_buys', ['store_id'])

    op.add_column('ai_strategy_reports', sa.Column('occasion', sa.String(length=255), nullable=True))
    op.add_column('ai_strategy_reports', sa.Column('strategy_type', sa.String(length=30), nullable=True))
    op.add_column('ai_strategy_reports', sa.Column('offline_plan', sa.Text(), nullable=True))
    op.add_column('ai_strategy_reports', sa.Column('online_plan', sa.Text(), nullable=True))
    op.add_column('ai_strategy_reports', sa.Column('vivino_listing', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('ai_strategy_reports', 'vivino_listing')
    op.drop_column('ai_strategy_reports', 'online_plan')
    op.drop_column('ai_strategy_reports', 'offline_plan')
    op.drop_column('ai_strategy_reports', 'strategy_type')
    op.drop_column('ai_strategy_reports', 'occasion')
    op.drop_index(op.f('ix_deal_buys_store_id'), table_name='deal_buys')
    op.drop_table('deal_buys')
