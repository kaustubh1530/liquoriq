"""phase 22b: owner-supplied gross margin

Revision ID: b8f4c2a91d7e
Revises: a3d9e51c7f24
Create Date: 2026-08-04

The POS export carries selling prices only, so every inventory figure is
computed at RETAIL. The dashboard was labelling those figures "cash frozen",
which overstates what the owner actually spent by his entire margin —
$220,661 of slow stock is nearer $154,000 of real cash at a 30% margin.

Nullable on purpose: unset means the dashboard shows retail value and no cost
figure at all, rather than inventing one from an industry average and
presenting it as his.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b8f4c2a91d7e'
down_revision: Union[str, None] = 'a3d9e51c7f24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'stores',
        sa.Column('gross_margin_pct', sa.Integer(), nullable=True,
                  comment='Gross margin %, owner-supplied. NULL = show retail only.'),
    )


def downgrade() -> None:
    op.drop_column('stores', 'gross_margin_pct')
