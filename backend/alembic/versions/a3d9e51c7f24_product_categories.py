"""phase 22: product category intelligence cache

Revision ID: a3d9e51c7f24
Revises: f2b71c8e4a93
Create Date: 2026-08-03

Tiers 1 and 2 of the category cascade. Keyed by SKU (falling back to the
product name) because names get re-typed between exports while the UPC is
stable. source="manual" marks an owner correction, which outranks every
automatic tier permanently.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'a3d9e51c7f24'
down_revision: Union[str, None] = 'f2b71c8e4a93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'product_categories',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('store_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('product_key', sa.String(length=200), nullable=False),
        sa.Column('product_name', sa.String(length=500), nullable=False, server_default=''),
        sa.Column('category', sa.String(length=40), nullable=False),
        sa.Column('brand', sa.String(length=80), nullable=True),
        sa.Column('source', sa.String(length=20), nullable=False, server_default='dictionary'),
        sa.Column('confidence', sa.String(length=10), nullable=False, server_default='medium'),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('store_id', 'product_key', name='uq_product_category_key'),
    )
    op.create_index('ix_product_categories_store_id', 'product_categories', ['store_id'])


def downgrade() -> None:
    op.drop_index('ix_product_categories_store_id', table_name='product_categories')
    op.drop_table('product_categories')
