"""add final_image_url and price_items to ad_creatives

Revision ID: e5a91b3c2d47
Revises: c8f2a41d7e93
Create Date: 2026-07-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5a91b3c2d47'
down_revision: Union[str, None] = 'c8f2a41d7e93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('ad_creatives', sa.Column(
        'final_image_url', sa.String(length=500), nullable=True,
        comment='Composed ad with deterministic price overlay'))
    op.add_column('ad_creatives', sa.Column(
        'price_items', sa.JSON(), nullable=True,
        comment='[{"product_name": str, "price": float}] used in the overlay'))


def downgrade() -> None:
    op.drop_column('ad_creatives', 'price_items')
    op.drop_column('ad_creatives', 'final_image_url')
