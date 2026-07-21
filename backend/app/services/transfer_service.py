"""
services/transfer_service.py — Exchange partner ledger logic (Phase 14)

Digitizes the pilot owner's real workflow at ~$80-90k/month per store:
exchanges with named partner stores (on-app or off-app), recorded at
WHOLESALE cost in either direction, with derived balances, monthly
statements with carry-forward, settlements, and undo.

Money-math rules:
  - line totals computed SERVER-side (client can't send a wrong total)
  - balances always DERIVED from raw records (undo self-heals everything)
  - pure functions for the math → unit-tested without a DB
  - balance > 0 → OUR store owes the partner; < 0 → they owe us
"""

import logging
import uuid
from collections import defaultdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.store import Store
from app.models.transfer import SettlementPayment, Transfer, TransferItem, TransferPartner
from app.models.user import User

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Pure math (unit-tested without a DB)
# ═══════════════════════════════════════════════════════════════════════════════

def compute_ledger(transfers: list[dict], payments: list[dict]) -> dict:
    """
    transfers: {direction: 'outgoing'|'incoming', transfer_date: date, total: float}
    payments:  {payer: 'me'|'partner', amount: float, paid_on: date}
    """
    sent_total = received_total = 0.0
    monthly: dict[str, dict] = defaultdict(lambda: {"sent": 0.0, "received": 0.0})

    for t in transfers:
        month = t["transfer_date"].strftime("%Y-%m")
        if t["direction"] == "outgoing":
            sent_total += t["total"]
            monthly[month]["sent"] += t["total"]
        else:
            received_total += t["total"]
            monthly[month]["received"] += t["total"]

    paid_out = sum(p["amount"] for p in payments if p["payer"] == "me")
    paid_in = sum(p["amount"] for p in payments if p["payer"] == "partner")

    balance = (received_total - sent_total) - paid_out + paid_in

    months = [
        {"month": m, "sent": round(v["sent"], 2), "received": round(v["received"], 2),
         "net": round(v["received"] - v["sent"], 2)}
        for m, v in sorted(monthly.items(), reverse=True)
    ]

    return {
        "sent_total": round(sent_total, 2),
        "received_total": round(received_total, 2),
        "paid_out": round(paid_out, 2),
        "paid_in": round(paid_in, 2),
        "balance": round(balance, 2),
        "months": months,
    }


def compute_monthly_report(month: str, transfers: list[dict], payments: list[dict]) -> dict:
    """
    Month statement: opening (carry-forward from all prior records),
    month activity, closing = opening + (received − sent) − paid_out + paid_in.
    """
    def in_month(d: date) -> bool:
        return d.strftime("%Y-%m") == month

    def before_month(d: date) -> bool:
        return d.strftime("%Y-%m") < month

    opening = compute_ledger(
        [t for t in transfers if before_month(t["transfer_date"])],
        [p for p in payments if before_month(p["paid_on"])],
    )["balance"]

    month_sent = sum(t["total"] for t in transfers if in_month(t["transfer_date"]) and t["direction"] == "outgoing")
    month_received = sum(t["total"] for t in transfers if in_month(t["transfer_date"]) and t["direction"] == "incoming")
    payments_out = sum(p["amount"] for p in payments if in_month(p["paid_on"]) and p["payer"] == "me")
    payments_in = sum(p["amount"] for p in payments if in_month(p["paid_on"]) and p["payer"] == "partner")

    closing = opening + (month_received - month_sent) - payments_out + payments_in

    return {
        "month": month,
        "opening_balance": round(opening, 2),
        "month_sent": round(month_sent, 2),
        "month_received": round(month_received, 2),
        "month_net": round(month_received - month_sent, 2),
        "payments_out": round(payments_out, 2),
        "payments_in": round(payments_in, 2),
        "closing_balance": round(closing, 2),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Partners
# ═══════════════════════════════════════════════════════════════════════════════

async def create_partner(current_store: Store, name: str, code: str | None, db: AsyncSession) -> dict:
    """
    Add an exchange partner. If a code is given it must match a real LiquorIQ
    store's exchange_code (security key) → the partner is LINKED. Without a
    code, we generate one for the relationship (hand it to the partner).
    """
    linked_store_id = None
    partner_code = uuid.uuid4().hex[:8].upper()

    if code:
        cleaned = code.strip().upper()
        result = await db.execute(select(Store).where(Store.exchange_code == cleaned))
        target = result.scalar_one_or_none()
        if target is None:
            raise ValueError("That exchange code doesn't match any store. Check with the partner.")
        if target.id == current_store.id:
            raise ValueError("That's this store's own code — enter the PARTNER's code.")
        linked_store_id = target.id
        partner_code = cleaned

    partner = TransferPartner(
        store_id=current_store.id,
        name=name.strip(),
        partner_code=partner_code,
        linked_store_id=linked_store_id,
    )
    db.add(partner)
    await db.commit()
    await db.refresh(partner)
    logger.info("Partner added: %s (linked=%s) for store %s", partner.name, bool(linked_store_id), current_store.id)
    return _partner_out(partner)


def _partner_out(p: TransferPartner) -> dict:
    return {
        "id": p.id, "name": p.name, "partner_code": p.partner_code,
        "linked": p.linked_store_id is not None,
        "is_active": p.is_active, "created_at": p.created_at,
    }


async def list_partners(current_store: Store, db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(TransferPartner)
        .where(TransferPartner.store_id == current_store.id, TransferPartner.is_active.is_(True))
        .order_by(TransferPartner.created_at)
    )
    return [_partner_out(p) for p in result.scalars().all()]


async def _get_partner(current_store: Store, partner_id: uuid.UUID, db: AsyncSession) -> TransferPartner:
    result = await db.execute(
        select(TransferPartner).where(
            TransferPartner.id == partner_id,
            TransferPartner.store_id == current_store.id,
        )
    )
    partner = result.scalar_one_or_none()
    if partner is None:
        raise ValueError("Partner not found for this store.")
    return partner


async def deactivate_partner(current_store: Store, partner_id: uuid.UUID, db: AsyncSession) -> None:
    partner = await _get_partner(current_store, partner_id, db)
    partner.is_active = False
    await db.commit()


# ═══════════════════════════════════════════════════════════════════════════════
# Transfers
# ═══════════════════════════════════════════════════════════════════════════════

def _serialize(t: Transfer) -> dict:
    total = float(sum(i.line_total for i in t.items))
    return {
        "id": t.id,
        "partner_id": t.partner_id,
        "partner_name": t.partner.name,
        "direction": t.direction,
        "transfer_date": t.transfer_date,
        "note": t.note,
        "total": round(total, 2),
        "items": t.items,
        "created_at": t.created_at,
    }


async def create_transfer(
    current_store: Store,
    user: User,
    partner_id: uuid.UUID,
    direction: str,
    items: list[dict],
    transfer_date: date | None,
    note: str | None,
    db: AsyncSession,
) -> dict:
    await _get_partner(current_store, partner_id, db)

    transfer = Transfer(
        store_id=current_store.id,
        partner_id=partner_id,
        direction=direction,
        transfer_date=transfer_date or date.today(),
        note=note,
        created_by_user_id=user.id,
    )
    for item in items:
        transfer.items.append(TransferItem(
            product_name=item["product_name"].strip(),
            sku=(item.get("sku") or None),
            quantity=item["quantity"],
            unit_cost=item["unit_cost"],
            line_total=round(item["quantity"] * item["unit_cost"], 2),
        ))
    db.add(transfer)
    await db.commit()

    result = await db.execute(select(Transfer).where(Transfer.id == transfer.id))
    return _serialize(result.scalar_one())


async def list_transfers(
    current_store: Store, db: AsyncSession,
    partner_id: uuid.UUID | None = None, limit: int = 200,
) -> list[dict]:
    query = (
        select(Transfer)
        .where(Transfer.store_id == current_store.id)
        .order_by(Transfer.transfer_date.desc(), Transfer.created_at.desc())
        .limit(limit)
    )
    if partner_id:
        query = query.where(Transfer.partner_id == partner_id)
    result = await db.execute(query)
    return [_serialize(t) for t in result.scalars().all()]


# ═══════════════════════════════════════════════════════════════════════════════
# Ledger / payments / report
# ═══════════════════════════════════════════════════════════════════════════════

async def _raw_records(current_store: Store, partner: TransferPartner, db: AsyncSession):
    t_result = await db.execute(
        select(Transfer)
        .where(Transfer.store_id == current_store.id, Transfer.partner_id == partner.id)
        .order_by(Transfer.transfer_date, Transfer.created_at)
    )
    p_result = await db.execute(
        select(SettlementPayment)
        .where(SettlementPayment.store_id == current_store.id,
               SettlementPayment.partner_id == partner.id)
        .order_by(SettlementPayment.paid_on)
    )
    return list(t_result.scalars().all()), list(p_result.scalars().all())


def _transfer_dicts(objs: list[Transfer]) -> list[dict]:
    return [
        {"direction": t.direction, "transfer_date": t.transfer_date,
         "total": float(sum(i.line_total for i in t.items))}
        for t in objs
    ]


def _payment_dicts(objs: list[SettlementPayment]) -> list[dict]:
    return [{"payer": p.payer, "amount": float(p.amount), "paid_on": p.paid_on} for p in objs]


async def get_ledger(current_store: Store, partner_id: uuid.UUID, db: AsyncSession) -> dict:
    partner = await _get_partner(current_store, partner_id, db)
    transfer_objs, payment_objs = await _raw_records(current_store, partner, db)
    ledger = compute_ledger(_transfer_dicts(transfer_objs), _payment_dicts(payment_objs))
    ledger["partner_id"] = partner.id
    ledger["partner_name"] = partner.name
    return ledger


async def get_monthly_report(
    current_store: Store, partner_id: uuid.UUID, month: str, db: AsyncSession,
) -> dict:
    partner = await _get_partner(current_store, partner_id, db)
    transfer_objs, payment_objs = await _raw_records(current_store, partner, db)

    report = compute_monthly_report(
        month, _transfer_dicts(transfer_objs), _payment_dicts(payment_objs)
    )
    report["store_name"] = current_store.name
    report["partner_id"] = partner.id
    report["partner_name"] = partner.name
    report["transfers"] = [
        {
            "transfer_date": t.transfer_date,
            "direction": t.direction,
            "items": t.items,
            "total": round(float(sum(i.line_total for i in t.items)), 2),
            "note": t.note,
        }
        for t in transfer_objs
        if t.transfer_date.strftime("%Y-%m") == month
    ]
    return report


async def list_payments(current_store: Store, partner_id: uuid.UUID, db: AsyncSession):
    partner = await _get_partner(current_store, partner_id, db)
    result = await db.execute(
        select(SettlementPayment)
        .where(SettlementPayment.store_id == current_store.id,
               SettlementPayment.partner_id == partner.id)
        .order_by(SettlementPayment.paid_on.desc(), SettlementPayment.created_at.desc())
    )
    return list(result.scalars().all())


async def record_payment(
    current_store: Store, user: User, partner_id: uuid.UUID,
    amount: float, payer: str, paid_on: date | None, note: str | None,
    db: AsyncSession,
) -> SettlementPayment:
    await _get_partner(current_store, partner_id, db)
    payment = SettlementPayment(
        store_id=current_store.id,
        partner_id=partner_id,
        payer=payer,
        amount=amount,
        paid_on=paid_on or date.today(),
        note=note,
        created_by_user_id=user.id,
    )
    db.add(payment)
    await db.commit()
    await db.refresh(payment)
    return payment


async def delete_payment(current_store: Store, payment_id: uuid.UUID, db: AsyncSession) -> None:
    """Undo a settlement payment — the derived balance self-corrects."""
    result = await db.execute(
        select(SettlementPayment).where(
            SettlementPayment.id == payment_id,
            SettlementPayment.store_id == current_store.id,
        )
    )
    payment = result.scalar_one_or_none()
    if payment is None:
        raise ValueError("Payment not found for this store.")
    await db.delete(payment)
    await db.commit()
