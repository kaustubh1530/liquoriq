"""strategy target segment + audience snapshot

Revision ID: f1a3c8e290d4
Revises: d92f7a4b1c60
Create Date: 2026-07-25

Phase 20: segment-targeted AI strategies. Both columns are NULLABLE — existing
strategies (no target) stay valid (backward compatible).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f1a3c8e290d4'
down_revision: Union[str, None] = 'd92f7a4b1c60'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('ai_strategy_reports', sa.Column('target_segment', sa.String(length=30), nullable=True))
    op.add_column('ai_strategy_reports', sa.Column('audience_snapshot', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('ai_strategy_reports', 'audience_snapshot')
    op.drop_column('ai_strategy_reports', 'target_segment')
