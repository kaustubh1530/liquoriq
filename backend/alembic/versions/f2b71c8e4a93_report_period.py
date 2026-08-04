"""phase 22: preserve the reporting period on uploads

Revision ID: f2b71c8e4a93
Revises: e7c93f2b1a06
Create Date: 2026-08-03

The AdvEntPOS parser already matched "From 01-Jul-2026 To 31-Jul-2026" but kept
only the end date, so every velocity calculation divided by a hard-coded 4.3
weeks. A WEEKLY upload therefore understated velocity 4x and made reorder,
dead-stock and overstock verdicts wrong. Storing the real window fixes all of
them at once.

period_estimated marks uploads where the file stated no period and we fell back
to 30 days, so the UI can say "estimated" rather than implying certainty.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f2b71c8e4a93'
down_revision: Union[str, None] = 'e7c93f2b1a06'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('uploaded_reports', sa.Column('period_start', sa.Date(), nullable=True))
    op.add_column('uploaded_reports', sa.Column('period_end', sa.Date(), nullable=True))
    op.add_column('uploaded_reports', sa.Column('period_days', sa.Integer(), nullable=True))
    op.add_column('uploaded_reports',
                  sa.Column('period_estimated', sa.Boolean(), nullable=False,
                            server_default=sa.text('false')))


def downgrade() -> None:
    op.drop_column('uploaded_reports', 'period_estimated')
    op.drop_column('uploaded_reports', 'period_days')
    op.drop_column('uploaded_reports', 'period_end')
    op.drop_column('uploaded_reports', 'period_start')
