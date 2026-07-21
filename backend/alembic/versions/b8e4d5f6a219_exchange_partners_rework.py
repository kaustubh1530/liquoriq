"""exchange partners rework

Revision ID: b8e4d5f6a219
Revises: f3d82c1a9b47
Create Date: 2026-07-20

Phase 14 (partner model): transfers now happen with named PARTNERS (any store,
on-app or off-app) instead of only sibling stores. The just-created ledger
tables are empty, so they are dropped and recreated in the new shape.
  - stores.exchange_code (unique security key, backfilled for existing rows)
  - transfer_partners
  - transfers: store_id + partner_id + direction (was from/to store pair)
  - settlement_payments: store_id + partner_id + payer 'me'/'partner'
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8e4d5f6a219'
down_revision: Union[str, None] = 'f3d82c1a9b47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── stores.exchange_code + backfill ──────────────────────────────────────
    op.add_column('stores', sa.Column('exchange_code', sa.String(length=16), nullable=True))
    op.execute("UPDATE stores SET exchange_code = upper(substr(md5(random()::text || id::text), 1, 8))")
    op.create_unique_constraint('uq_stores_exchange_code', 'stores', ['exchange_code'])

    # ── drop the pair-based tables (empty — created earlier this phase) ──────
    op.drop_table('transfer_items')
    op.drop_table('settlement_payments')
    op.drop_table('transfers')

    # ── transfer_partners ────────────────────────────────────────────────────
    op.create_table('transfer_partners',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('store_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('partner_code', sa.String(length=16), nullable=False),
        sa.Column('linked_store_id', sa.UUID(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['linked_store_id'], ['stores.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_transfer_partners_store_id'), 'transfer_partners', ['store_id'])

    # ── transfers (partner + direction shape) ────────────────────────────────
    op.create_table('transfers',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('store_id', sa.UUID(), nullable=False),
        sa.Column('partner_id', sa.UUID(), nullable=False),
        sa.Column('direction', sa.String(length=10), nullable=False,
                  comment='outgoing = we sent stock to the partner; incoming = we received'),
        sa.Column('transfer_date', sa.Date(), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_by_user_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['partner_id'], ['transfer_partners.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_transfers_store_id'), 'transfers', ['store_id'])
    op.create_index(op.f('ix_transfers_partner_id'), 'transfers', ['partner_id'])
    op.create_index(op.f('ix_transfers_transfer_date'), 'transfers', ['transfer_date'])

    # ── transfer_items (unchanged shape) ─────────────────────────────────────
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

    # ── settlement_payments (payer me/partner shape) ─────────────────────────
    op.create_table('settlement_payments',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('store_id', sa.UUID(), nullable=False),
        sa.Column('partner_id', sa.UUID(), nullable=False),
        sa.Column('payer', sa.String(length=10), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('paid_on', sa.Date(), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_by_user_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['partner_id'], ['transfer_partners.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_settlement_payments_store_id'), 'settlement_payments', ['store_id'])
    op.create_index(op.f('ix_settlement_payments_partner_id'), 'settlement_payments', ['partner_id'])


def downgrade() -> None:
    op.drop_table('settlement_payments')
    op.drop_table('transfer_items')
    op.drop_table('transfers')
    op.drop_table('transfer_partners')
    op.drop_constraint('uq_stores_exchange_code', 'stores', type_='unique')
    op.drop_column('stores', 'exchange_code')
    # (pair-based tables from f3d82c1a9b47 are NOT recreated on downgrade)
