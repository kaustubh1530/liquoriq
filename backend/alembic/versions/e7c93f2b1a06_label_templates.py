"""label studio: saved style templates

Revision ID: e7c93f2b1a06
Revises: d1a58b04e7c3
Create Date: 2026-08-02

The owner sets up a look once ("our staff-pick style") and reuses it for any
bottle. A template is just a LabelDesign with is_template=true whose
product-specific fields are blank, so it needs no second table.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e7c93f2b1a06'
down_revision: Union[str, None] = 'd1a58b04e7c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('label_designs',
                  sa.Column('is_template', sa.Boolean(), nullable=False,
                            server_default=sa.text('false')))
    op.create_index('ix_label_designs_is_template', 'label_designs',
                    ['store_id', 'is_template'])


def downgrade() -> None:
    op.drop_index('ix_label_designs_is_template', table_name='label_designs')
    op.drop_column('label_designs', 'is_template')
