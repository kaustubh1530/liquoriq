"""label studio: shelf labels (base image no longer required)

Revision ID: d1a58b04e7c3
Revises: c9f42a17d3e5
Create Date: 2026-08-01

Label Studio became a SHELF LABEL maker: a label is a standalone printable card
(bottle name, rating, price) drawn on a clean background, not an overlay on a
photo. So base_image_url is now optional, and design_json holds the label spec.

Non-destructive: the column stays for any overlay design already saved.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd1a58b04e7c3'
down_revision: Union[str, None] = 'c9f42a17d3e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('label_designs', 'base_image_url',
                    existing_type=sa.String(length=500), nullable=True)


def downgrade() -> None:
    # Backfill so the NOT NULL can be restored without failing on shelf labels
    op.execute("UPDATE label_designs SET base_image_url = '' WHERE base_image_url IS NULL")
    op.alter_column('label_designs', 'base_image_url',
                    existing_type=sa.String(length=500), nullable=False)
