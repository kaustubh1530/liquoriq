"""
schemas/transfer.py — Exchange partners + transfer ledger shapes (Phase 14)

POST /transfers/partners               → PartnerResponse (201)
GET  /transfers/partners               → list[PartnerResponse]
POST /transfers                        → TransferResponse (201)
GET  /transfers?partner_id=            → list[TransferResponse]
GET  /transfers/ledger/{partner_id}    → LedgerResponse
GET  /transfers/payments/{partner_id}  → list[PaymentResponse]
POST /transfers/settle/{partner_id}    → PaymentResponse (owner only)
DELETE /transfers/payments/{id}        → 204 (owner only, "undo")
GET  /transfers/report/{partner_id}?month=YYYY-MM[&format=csv]
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


# ─── Partners ─────────────────────────────────────────────────────────────────

class PartnerCreate(BaseModel):
    """
    Add an exchange partner by name. If the partner uses LiquorIQ, enter the
    exchange code THEY gave you — it validates and links the accounts. Without
    a code, a partner_code is generated for you to hand to them.
    """
    name: str = Field(min_length=2, max_length=255)
    code: str | None = Field(default=None, max_length=16,
                             description="The partner store's exchange code (optional)")


class PartnerResponse(BaseModel):
    id: uuid.UUID
    name: str
    partner_code: str
    linked: bool = False        # True when tied to a real LiquorIQ store
    is_active: bool
    created_at: datetime


# ─── Transfers ────────────────────────────────────────────────────────────────

class TransferItemIn(BaseModel):
    product_name: str = Field(min_length=1, max_length=500)
    sku: str | None = Field(default=None, max_length=100)
    quantity: float = Field(gt=0, lt=100_000)
    unit_cost: float = Field(ge=0, lt=100_000, description="Wholesale cost per unit")


class TransferCreate(BaseModel):
    partner_id: uuid.UUID
    direction: str = Field(pattern="^(outgoing|incoming)$",
                           description="outgoing = we send to the partner; incoming = we receive")
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
    partner_id: uuid.UUID
    partner_name: str
    direction: str
    transfer_date: date
    note: str | None
    total: float
    items: list[TransferItemOut]
    created_at: datetime


# ─── Ledger / settlement ──────────────────────────────────────────────────────

class LedgerMonth(BaseModel):
    month: str                  # "2026-07"
    sent: float
    received: float
    net: float                  # received − sent (positive = we owe for this month)


class LedgerResponse(BaseModel):
    partner_id: uuid.UUID
    partner_name: str
    sent_total: float
    received_total: float
    paid_out: float
    paid_in: float
    balance: float              # >0: WE owe the partner; <0: they owe us
    months: list[LedgerMonth]   # newest first


class PaymentCreate(BaseModel):
    amount: float = Field(gt=0, lt=10_000_000)
    payer: str = Field(pattern="^(me|partner)$",
                       description="'me' = our store pays; 'partner' = they pay us")
    paid_on: date | None = None
    note: str | None = None


class PaymentResponse(BaseModel):
    id: uuid.UUID
    partner_id: uuid.UUID
    payer: str
    amount: float
    paid_on: date
    note: str | None

    model_config = {"from_attributes": True}


# ─── Monthly report ───────────────────────────────────────────────────────────

class ReportTransferLine(BaseModel):
    transfer_date: date
    direction: str              # "outgoing" | "incoming"
    items: list[TransferItemOut]
    total: float
    note: str | None = None


class MonthlyReportResponse(BaseModel):
    """
    End-of-month statement for one partner — mirrors the manual tally:
    opening balance (carry-forward), month activity, closing balance.
    Positive balances = WE owe the partner.
    """
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
