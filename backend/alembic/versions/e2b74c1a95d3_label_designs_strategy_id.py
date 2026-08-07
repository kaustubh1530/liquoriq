"""phase 23.8: link a shelf label to the campaign it was made for

Revision ID: e2b74c1a95d3
Revises: d5a1f39c8b02
Create Date: 2026-08-07

Phase 23.7 shipped a labels step that could only ask "does this shop have ANY
saved label?" — flagged `weak: true` in the payload rather than dressed up as
something better. That is the last unhonest square on the progress bar: a label
made for July's clearance marked June's Father's Day campaign complete.

NULLABLE, and deliberately so. The Label Studio is also a standalone tool: a
shelf tag for a bottle nobody is running a campaign on is a legitimate label,
not an orphan. Making this NOT NULL would force every such label to belong to a
campaign that does not exist.

SET NULL on delete, matching creative_id above it. A label is a PHYSICAL thing —
it is printed and clipped to a shelf. Deleting the strategy that inspired it
must not delete the design of a card that is still hanging in the aisle.

Existing rows keep strategy_id NULL. They are not backfilled: we have no record
of which campaign an old label was for, and inventing that link would put the
guess somewhere it can never be told apart from a fact.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'e2b74c1a95d3'
down_revision: Union[str, None] = 'd5a1f39c8b02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'label_designs',
        sa.Column('strategy_id', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        'fk_label_designs_strategy_id', 'label_designs', 'ai_strategy_reports',
        ['strategy_id'], ['id'], ondelete='SET NULL',
    )
    op.create_index('ix_label_designs_strategy_id', 'label_designs', ['strategy_id'])


def downgrade() -> None:
    op.drop_index('ix_label_designs_strategy_id', table_name='label_designs')
    op.drop_constraint('fk_label_designs_strategy_id', 'label_designs',
                       type_='foreignkey')
    op.drop_column('label_designs', 'strategy_id')
