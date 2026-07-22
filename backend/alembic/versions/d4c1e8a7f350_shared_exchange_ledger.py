"""shared exchange ledger with audit

Revision ID: d4c1e8a7f350
Revises: b8e4d5f6a219
Create Date: 2026-07-20

Phase 14 (shared model): exchanges are now a SHARED ledger between two
LiquorIQ stores (both must be linked via mandatory exchange codes), keyed by
store pair, with created-by / deleted-by audit trails and soft-delete undo.
The partner-shape tables are empty, so they're dropped and recreated.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4c1e8a7f350'
down_revision: Union[str, None] = 'b8e4d5f6a219'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop partner-shape tables (empty)
    op.drop_table('settlement_payments')
    op.drop_table('transfer_items')
    op.drop_table('transfers')
    op.drop_table('transfer_partners')

    # ── transfer_partners: mandatory link to a real store, no code column ────
    op.create_table('transfer_partners',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('store_id', sa.UUID(), nullable=False),
        sa.Column('linked_store_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['linked_store_id'], ['stores.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_transfer_partners_store_id'), 'transfer_partners', ['store_id'])

    # ── transfers: store pair + audit + soft delete ──────────────────────────
    op.create_table('transfers',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('from_store_id', sa.UUID(), nullable=False),
        sa.Column('to_store_id', sa.UUID(), nullable=False),
        sa.Column('transfer_date', sa.Date(), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_by_user_id', sa.UUID(), nullable=True),
        sa.Column('created_by_store_id', sa.UUID(), nullable=True),
        sa.Column('created_by_label', sa.String(length=320), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('deleted_by_label', sa.String(length=320), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['from_store_id'], ['stores.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['to_store_id'], ['stores.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by_store_id'], ['stores.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_transfers_from_store_id'), 'transfers', ['from_store_id'])
    op.create_index(op.f('ix_transfers_to_store_id'), 'transfers', ['to_store_id'])
    op.create_index(op.f('ix_transfers_transfer_date'), 'transfers', ['transfer_date'])

    op.create_table('transfer_items',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('transfer_id', sa.UUID(), nullable=False),
        sa.Column('product_name', sa.String(length=500), nullable=False),
        sa.Column('sku', sa.String(length=100), nullable=True),
        sa.Column('quantity', sa.Numeric(12, 3), nullable=False),
        sa.Column('unit_cost', sa.Numeric(12, 2), nullable=False,
                  comment='WHOLESALE cost per unit — exchanges settle at cost'),
        sa.Column('line_total', sa.Numeric(12, 2), nullable=False),
        sa.ForeignKeyConstraint(['transfer_id'], ['transfers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_transfer_items_transfer_id'), 'transfer_items', ['transfer_id'])

    op.create_table('settlement_payments',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('from_store_id', sa.UUID(), nullable=False),
        sa.Column('to_store_id', sa.UUID(), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('paid_on', sa.Date(), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_by_user_id', sa.UUID(), nullable=True),
        sa.Column('created_by_store_id', sa.UUID(), nullable=True),
        sa.Column('created_by_label', sa.String(length=320), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('deleted_by_label', sa.String(length=320), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['from_store_id'], ['stores.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['to_store_id'], ['stores.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by_store_id'], ['stores.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_settlement_payments_from_store_id'), 'settlement_payments', ['from_store_id'])
    op.create_index(op.f('ix_settlement_payments_to_store_id'), 'settlement_payments', ['to_store_id'])


def downgrade() -> None:
    op.drop_table('settlement_payments')
    op.drop_table('transfer_items')
    op.drop_table('transfers')
    op.drop_table('transfer_partners')
