"""label studio: label_designs table

Revision ID: c9f42a17d3e5
Revises: b7e3f1a06c92
Create Date: 2026-07-31

MODULE SPLIT: the AI Ad Creator produces a finished ad; the Label Studio owns
promotional badges in its own table. label_designs.creative_id is SET NULL on
delete so a design outlives the ad it started from.

ad_creatives.design_json is intentionally LEFT IN PLACE (unused by the new code)
so this migration is non-destructive and trivially reversible.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'c9f42a17d3e5'
down_revision: Union[str, None] = 'b7e3f1a06c92'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'label_designs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('store_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('creative_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('name', sa.String(length=200), nullable=False,
                  server_default='Untitled design'),
        sa.Column('base_image_url', sa.String(length=500), nullable=False),
        sa.Column('final_image_url', sa.String(length=500), nullable=True),
        sa.Column('design_json', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['creative_id'], ['ad_creatives.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_label_designs_store_id', 'label_designs', ['store_id'])
    op.create_index('ix_label_designs_creative_id', 'label_designs', ['creative_id'])


def downgrade() -> None:
    op.drop_index('ix_label_designs_creative_id', table_name='label_designs')
    op.drop_index('ix_label_designs_store_id', table_name='label_designs')
    op.drop_table('label_designs')
