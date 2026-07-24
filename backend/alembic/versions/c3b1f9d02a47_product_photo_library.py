"""product photo library

Revision ID: c3b1f9d02a47
Revises: e7f1a9c3d820
Create Date: 2026-07-22

Phase 16: reusable product photos (upload once per product, auto-reused).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3b1f9d02a47'
down_revision: Union[str, None] = 'e7f1a9c3d820'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('product_photos',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('store_id', sa.UUID(), nullable=False),
        sa.Column('product_key', sa.String(length=500), nullable=False),
        sa.Column('product_name', sa.String(length=500), nullable=False),
        sa.Column('image_url', sa.String(length=500), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('store_id', 'product_key', name='uq_product_photo_store_key'),
    )
    op.create_index(op.f('ix_product_photos_store_id'), 'product_photos', ['store_id'])
    op.create_index(op.f('ix_product_photos_product_key'), 'product_photos', ['product_key'])


def downgrade() -> None:
    op.drop_index(op.f('ix_product_photos_product_key'), table_name='product_photos')
    op.drop_index(op.f('ix_product_photos_store_id'), table_name='product_photos')
    op.drop_table('product_photos')
