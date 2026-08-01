"""product facts + ad design plan/json

Revision ID: b7e3f1a06c92
Revises: a5d9c2e714b8
Create Date: 2026-07-26

Professional Ad Upgrade: reusable product facts + editable design plan/overlay.
Both ad_creatives columns are NULLABLE (old creatives stay valid).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7e3f1a06c92'
down_revision: Union[str, None] = 'a5d9c2e714b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('ad_creatives', sa.Column('design_plan', sa.JSON(), nullable=True))
    op.add_column('ad_creatives', sa.Column('design_json', sa.JSON(), nullable=True))

    op.create_table('product_facts',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('store_id', sa.UUID(), nullable=False),
        sa.Column('product_key', sa.String(length=500), nullable=False),
        sa.Column('product_name', sa.String(length=500), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('facts', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('store_id', 'product_key', name='uq_product_facts_store_key'),
    )
    op.create_index(op.f('ix_product_facts_store_id'), 'product_facts', ['store_id'])
    op.create_index(op.f('ix_product_facts_product_key'), 'product_facts', ['product_key'])


def downgrade() -> None:
    op.drop_index(op.f('ix_product_facts_product_key'), table_name='product_facts')
    op.drop_index(op.f('ix_product_facts_store_id'), table_name='product_facts')
    op.drop_table('product_facts')
    op.drop_column('ad_creatives', 'design_json')
    op.drop_column('ad_creatives', 'design_plan')
