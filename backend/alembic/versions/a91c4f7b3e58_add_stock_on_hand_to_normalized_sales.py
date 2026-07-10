"""add stock_on_hand to normalized_sales

Revision ID: a91c4f7b3e58
Revises: e5a91b3c2d47
Create Date: 2026-07-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a91c4f7b3e58'
down_revision: Union[str, None] = 'e5a91b3c2d47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('normalized_sales', sa.Column(
        'stock_on_hand', sa.Numeric(12, 3), nullable=True,
        comment='Inventory snapshot from the POS report (AdvEntPOS Stock-On-Hand)'))


def downgrade() -> None:
    op.drop_column('normalized_sales', 'stock_on_hand')
