"""customers and purchase history (RFM)

Revision ID: d92f7a4b1c60
Revises: c3b1f9d02a47
Create Date: 2026-07-25

Phase 19: customer ingestion + RFM segmentation.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd92f7a4b1c60'
down_revision: Union[str, None] = 'c3b1f9d02a47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('customers',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('store_id', sa.UUID(), nullable=False),
        sa.Column('dedup_key', sa.String(length=320), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('total_spent', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('purchase_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('first_purchase_date', sa.Date(), nullable=True),
        sa.Column('last_purchase_date', sa.Date(), nullable=True),
        sa.Column('sms_opt_in', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('email_opt_in', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('store_id', 'dedup_key', name='uq_customer_store_key'),
    )
    op.create_index(op.f('ix_customers_store_id'), 'customers', ['store_id'])
    op.create_index(op.f('ix_customers_dedup_key'), 'customers', ['dedup_key'])

    op.create_table('customer_purchases',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('store_id', sa.UUID(), nullable=False),
        sa.Column('customer_id', sa.UUID(), nullable=False),
        sa.Column('purchase_date', sa.Date(), nullable=True),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('product_name', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_customer_purchases_store_id'), 'customer_purchases', ['store_id'])
    op.create_index(op.f('ix_customer_purchases_customer_id'), 'customer_purchases', ['customer_id'])


def downgrade() -> None:
    op.drop_table('customer_purchases')
    op.drop_table('customers')
