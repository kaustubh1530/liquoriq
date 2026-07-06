"""add ad_creatives table

Revision ID: c8f2a41d7e93
Revises: a57934a141b2
Create Date: 2026-07-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8f2a41d7e93'
down_revision: Union[str, None] = 'a57934a141b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('ad_creatives',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('store_id', sa.UUID(), nullable=False),
    sa.Column('strategy_id', sa.UUID(), nullable=False),
    sa.Column('image_prompt', sa.Text(), nullable=False, comment='The exact prompt sent to DALL-E 3'),
    sa.Column('image_url', sa.String(length=500), nullable=False, comment='Relative URL, e.g. /static/creatives/<uuid>.png'),
    sa.Column('instagram_caption', sa.Text(), nullable=False),
    sa.Column('facebook_post', sa.Text(), nullable=False),
    sa.Column('ubereats_description', sa.Text(), nullable=False),
    sa.Column('doordash_description', sa.Text(), nullable=False),
    sa.Column('website_banner_headline', sa.String(length=200), nullable=False),
    sa.Column('website_banner_text', sa.Text(), nullable=False),
    sa.Column('model_used', sa.String(length=100), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['strategy_id'], ['ai_strategy_reports.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ad_creatives_store_id'), 'ad_creatives', ['store_id'], unique=False)
    op.create_index(op.f('ix_ad_creatives_strategy_id'), 'ad_creatives', ['strategy_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_ad_creatives_strategy_id'), table_name='ad_creatives')
    op.drop_index(op.f('ix_ad_creatives_store_id'), table_name='ad_creatives')
    op.drop_table('ad_creatives')
