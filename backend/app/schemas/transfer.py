"""
schemas/transfer.py — Shared exchange ledger shapes (Phase 14, shared model)

POST   /transfers/partners             → PartnerResponse (201)   (code mandatory)
GET    /transfers/partners             → list[PartnerResponse]
DELETE /transfers/partners/{id}        → 204
POST   /transfers                      → TransferResponse (201)
GET    /transfers?partner_id=          → list[TransferResponse]  (shared history)
DELETE /transfers/{id}                 → 204   (undo, audited)
GET    /transfers/ledger/{partner_id}  → LedgerResponse
GET    /transfers/payments/{partner_id}→ list[PaymentResponse]
POST   /transfers/settle/{partner_id}  → PaymentResponse         (owner only)
DELETE /transfers/payments/{id}        → 204   (undo, owner only)
GET    /transfers/report/{partner_id}?month=YYYY-MM[&format=csv]
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


# ─── Partners ─────────────────────────────────────────────────────────────────

class PartnerCreate(BaseModel):
    code: str = Field(min_length=4, max_length=16,
                      description="The partner store's exchange code (mandatory)")
    name: str | None = Field(default=None, max_length=255,
                             description="Display name (defaults to the linked store's name)")


class PartnerResponse(BaseModel):
    id: uuid.UUID
    name: str
    linked_store_id: uuid.UUID
    mutual: bool = False        # True once the partner has added us back
    is_active: bool
    created_at: datetime


# ─── Transfers ────────────────────────────────────────────────────────────────

class TransferItemIn(BaseModel):
    product_name: str = Field(min_length=1, max_length=500)
    sku: str | None = Field(default=None, max_length=100)
    quantity: float = Field(gt=0, lt=100_000)
    unit_cost: float = Field(ge=0, lt=100_000)


class TransferCreate(BaseModel):
    partner_id: uuid.UUID
    direction: str = Field(pattern="^(outgoing|incoming)$")
    transfer_date: date | None = None
    note: str | None = None
    items: list[TransferItemIn] = Field(min_length=1, max_length=200)


class TransferItemOut(BaseModel):
    product_name: str
    sku: str | None
    quantity: float
    unit_cost: float
    line_total: float

    model_config = {"from_attributes": True}


class TransferResponse(BaseModel):
    id: uuid.UUID
    direction: str
    transfer_date: date
    note: str | None
    total: float
    items: list[TransferItemOut]
    created_by_label: str | None = None    # audit: who added it
    is_deleted: bool = False
    deleted_by_label: str | None = None    # audit: who removed it
    created_at: datetime


# ─── Ledger / settlement ──────────────────────────────────────────────────────

class LedgerMonth(BaseModel):
    month: str
    sent: float
    received: float
    net: float


class LedgerResponse(BaseModel):
    partner_id: uuid.UUID
    partner_name: str
    sent_total: float
    received_total: float
    paid_out: float
    paid_in: float
    balance: float
    months: list[LedgerMonth]


class PaymentCreate(BaseModel):
    amount: float = Field(gt=0, lt=10_000_000)
    payer: str = Field(pattern="^(me|partner)$")
    paid_on: date | None = None
    note: str | None = None


class PaymentResponse(BaseModel):
    id: uuid.UUID
    payer: str
    amount: float
    paid_on: date
    note: str | None
    created_by_label: str | None = None


# ─── Monthly report ───────────────────────────────────────────────────────────

class ReportTransferLine(BaseModel):
    transfer_date: date
    direction: str
    items: list[TransferItemOut]
    total: float
    note: str | None = None


class MonthlyReportResponse(BaseModel):
    month: str
    store_name: str
    partner_id: uuid.UUID
    partner_name: str
    opening_balance: float
    month_sent: float
    month_received: float
    month_net: float
    payments_out: float
    payments_in: float
    closing_balance: float
    transfers: list[ReportTransferLine]
