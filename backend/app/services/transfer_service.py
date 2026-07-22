"""
services/transfer_service.py — Shared exchange ledger logic (Phase 14, shared model)

Two LiquorIQ stores share one ledger (linked via mandatory exchange codes).
Records are keyed by the real store PAIR, so both members see the same rows.
Every row is audited (who added / who removed). Undo is a soft delete.

Money-math rules (pilot moves ~$80-90k/month per store):
  - line totals computed SERVER-side
  - balances DERIVED from NON-DELETED rows only (undo self-heals)
  - pure functions do the math, converted to "current store's view" first
  - balance > 0 → OUR store owes the partner; < 0 → they owe us
"""

import logging
import uuid
from collections import defaultdict
from datetime import date, datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.store import Store
from app.models.transfer import SettlementPayment, Transfer, TransferItem, TransferPartner
from app.models.user import User

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Pure math (unit-tested; operates on "me-relative" dicts)
# ═══════════════════════════════════════════════════════════════════════════════

def compute_ledger(transfers: list[dict], payments: list[dict]) -> dict:
    """transfers: {direction:'outgoing'|'incoming', transfer_date, total};
       payments:  {payer:'me'|'partner', amount, paid_on}"""
    sent_total = received_total = 0.0
    monthly: dict[str, dict] = defaultdict(lambda: {"sent": 0.0, "received": 0.0})

    for t in transfers:
        month = t["transfer_date"].strftime("%Y-%m")
        if t["direction"] == "outgoing":
            sent_total += t["total"]; monthly[month]["sent"] += t["total"]
        else:
            received_total += t["total"]; monthly[month]["received"] += t["total"]

    paid_out = sum(p["amount"] for p in payments if p["payer"] == "me")
    paid_in = sum(p["amount"] for p in payments if p["payer"] == "partner")
    balance = (received_total - sent_total) - paid_out + paid_in

    months = [
        {"month": m, "sent": round(v["sent"], 2), "received": round(v["received"], 2),
         "net": round(v["received"] - v["sent"], 2)}
        for m, v in sorted(monthly.items(), reverse=True)
    ]
    return {
        "sent_total": round(sent_total, 2), "received_total": round(received_total, 2),
        "paid_out": round(paid_out, 2), "paid_in": round(paid_in, 2),
        "balance": round(balance, 2), "months": months,
    }


def compute_monthly_report(month: str, transfers: list[dict], payments: list[dict]) -> dict:
    def in_m(d): return d.strftime("%Y-%m") == month
    def before_m(d): return d.strftime("%Y-%m") < month

    opening = compute_ledger(
        [t for t in transfers if before_m(t["transfer_date"])],
        [p for p in payments if before_m(p["paid_on"])],
    )["balance"]

    ms = sum(t["total"] for t in transfers if in_m(t["transfer_date"]) and t["direction"] == "outgoing")
    mr = sum(t["total"] for t in transfers if in_m(t["transfer_date"]) and t["direction"] == "incoming")
    po = sum(p["amount"] for p in payments if in_m(p["paid_on"]) and p["payer"] == "me")
    pi = sum(p["amount"] for p in payments if in_m(p["paid_on"]) and p["payer"] == "partner")

    return {
        "month": month, "opening_balance": round(opening, 2),
        "month_sent": round(ms, 2), "month_received": round(mr, 2),
        "month_net": round(mr - ms, 2), "payments_out": round(po, 2),
        "payments_in": round(pi, 2),
        "closing_balance": round(opening + (mr - ms) - po + pi, 2),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Partners (mandatory code → link to a real store)
# ═══════════════════════════════════════════════════════════════════════════════

async def create_partner(current_store: Store, code: str, name: str | None, db: AsyncSession) -> dict:
    """Add an exchange partner by their store's exchange code (mandatory)."""
    cleaned = (code or "").strip().upper()
    if not cleaned:
        raise ValueError("An exchange code is required to add a partner.")

    result = await db.execute(select(Store).where(Store.exchange_code == cleaned))
    target = result.scalar_one_or_none()
    if target is None:
        raise ValueError("That exchange code doesn't match any store. Check with the partner.")
    if target.id == current_store.id:
        raise ValueError("That's this store's own code — enter the PARTNER's code.")

    # Prevent duplicates
    existing = await db.execute(
        select(TransferPartner).where(
            TransferPartner.store_id == current_store.id,
            TransferPartner.linked_store_id == target.id,
        )
    )
    dup = existing.scalar_one_or_none()
    if dup:
        if not dup.is_active:
            dup.is_active = True
            await db.commit()
            return _partner_out(dup, target)
        raise ValueError(f"{target.name} is already one of your exchange partners.")

    partner = TransferPartner(
        store_id=current_store.id,
        linked_store_id=target.id,
        name=(name or "").strip() or target.name,
    )
    db.add(partner)
    await db.commit()
    await db.refresh(partner)
    logger.info("Partner linked: store %s ↔ store %s", current_store.id, target.id)
    return _partner_out(partner, target)


def _partner_out(p: TransferPartner, linked: Store | None = None) -> dict:
    # `mutual` = does the OTHER store also have us as a partner? (set by caller)
    return {
        "id": p.id, "name": p.name, "linked_store_id": p.linked_store_id,
        "is_active": p.is_active, "created_at": p.created_at,
    }


async def list_partners(current_store: Store, db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(TransferPartner)
        .where(TransferPartner.store_id == current_store.id, TransferPartner.is_active.is_(True))
        .order_by(TransferPartner.created_at)
    )
    partners = list(result.scalars().all())

    # Compute `mutual`: has the linked store added us back? (they see the same ledger)
    out = []
    for p in partners:
        back = await db.execute(
            select(TransferPartner).where(
                TransferPartner.store_id == p.linked_store_id,
                TransferPartner.linked_store_id == current_store.id,
                TransferPartner.is_active.is_(True),
            )
        )
        d = _partner_out(p)
        d["mutual"] = back.scalar_one_or_none() is not None
        out.append(d)
    return out


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
# Transfers (shared, pair-keyed, audited, soft-deletable)
# ═══════════════════════════════════════════════════════════════════════════════

def _label(user: User, store: Store) -> str:
    return f"{user.full_name} · {store.name}"


def _serialize(t: Transfer, current_store_id: uuid.UUID) -> dict:
    total = float(sum(i.line_total for i in t.items))
    return {
        "id": t.id,
        "direction": "outgoing" if t.from_store_id == current_store_id else "incoming",
        "transfer_date": t.transfer_date,
        "note": t.note,
        "total": round(total, 2),
        "items": t.items,
        "created_by_label": t.created_by_label,
        "is_deleted": t.is_deleted,
        "deleted_by_label": t.deleted_by_label,
        "created_at": t.created_at,
    }


def _pair(a: uuid.UUID, b: uuid.UUID):
    return or_(
        (Transfer.from_store_id == a) & (Transfer.to_store_id == b),
        (Transfer.from_store_id == b) & (Transfer.to_store_id == a),
    )


def _pair_pay(a: uuid.UUID, b: uuid.UUID):
    return or_(
        (SettlementPayment.from_store_id == a) & (SettlementPayment.to_store_id == b),
        (SettlementPayment.from_store_id == b) & (SettlementPayment.to_store_id == a),
    )


async def create_transfer(
    current_store: Store, user: User, partner_id: uuid.UUID, direction: str,
    items: list[dict], transfer_date: date | None, note: str | None, db: AsyncSession,
) -> dict:
    partner = await _get_partner(current_store, partner_id, db)
    other_id = partner.linked_store_id
    from_id, to_id = (current_store.id, other_id) if direction == "outgoing" else (other_id, current_store.id)

    transfer = Transfer(
        from_store_id=from_id, to_store_id=to_id,
        transfer_date=transfer_date or date.today(), note=note,
        created_by_user_id=user.id, created_by_store_id=current_store.id,
        created_by_label=_label(user, current_store),
    )
    for item in items:
        transfer.items.append(TransferItem(
            product_name=item["product_name"].strip(),
            sku=(item.get("sku") or None),
            quantity=item["quantity"], unit_cost=item["unit_cost"],
            line_total=round(item["quantity"] * item["unit_cost"], 2),
        ))
    db.add(transfer)
    await db.commit()
    result = await db.execute(select(Transfer).where(Transfer.id == transfer.id))
    return _serialize(result.scalar_one(), current_store.id)


async def list_transfers(current_store: Store, partner_id: uuid.UUID, db: AsyncSession, limit: int = 300) -> list[dict]:
    """SHARED history for the pair — includes soft-deleted rows (marked) for audit."""
    partner = await _get_partner(current_store, partner_id, db)
    result = await db.execute(
        select(Transfer)
        .where(_pair(current_store.id, partner.linked_store_id))
        .order_by(Transfer.transfer_date.desc(), Transfer.created_at.desc())
        .limit(limit)
    )
    return [_serialize(t, current_store.id) for t in result.scalars().all()]


async def undo_transfer(current_store: Store, user: User, transfer_id: uuid.UUID, db: AsyncSession) -> None:
    """Soft-delete a transfer, recording who removed it. Either member store may."""
    result = await db.execute(
        select(Transfer).where(
            Transfer.id == transfer_id,
            or_(Transfer.from_store_id == current_store.id, Transfer.to_store_id == current_store.id),
        )
    )
    transfer = result.scalar_one_or_none()
    if transfer is None:
        raise ValueError("Transfer not found for this store.")
    if transfer.is_deleted:
        raise ValueError("This transfer was already removed.")
    transfer.is_deleted = True
    transfer.deleted_by_label = _label(user, current_store)
    transfer.deleted_at = datetime.now(timezone.utc)
    await db.commit()
    logger.info("Transfer %s removed by %s", transfer_id, transfer.deleted_by_label)


# ═══════════════════════════════════════════════════════════════════════════════
# Ledger / report / payments  (convert pair rows → current store's view)
# ═══════════════════════════════════════════════════════════════════════════════

async def _pair_records(current_store: Store, partner: TransferPartner, db: AsyncSession):
    other = partner.linked_store_id
    t_res = await db.execute(
        select(Transfer).where(_pair(current_store.id, other), Transfer.is_deleted.is_(False))
        .order_by(Transfer.transfer_date, Transfer.created_at)
    )
    p_res = await db.execute(
        select(SettlementPayment).where(_pair_pay(current_store.id, other), SettlementPayment.is_deleted.is_(False))
        .order_by(SettlementPayment.paid_on)
    )
    return list(t_res.scalars().all()), list(p_res.scalars().all())


def _t_view(objs, current_store_id):
    return [
        {"direction": "outgoing" if t.from_store_id == current_store_id else "incoming",
         "transfer_date": t.transfer_date, "total": float(sum(i.line_total for i in t.items))}
        for t in objs
    ]


def _p_view(objs, current_store_id):
    return [
        {"payer": "me" if p.from_store_id == current_store_id else "partner",
         "amount": float(p.amount), "paid_on": p.paid_on}
        for p in objs
    ]


async def get_ledger(current_store: Store, partner_id: uuid.UUID, db: AsyncSession) -> dict:
    partner = await _get_partner(current_store, partner_id, db)
    t_objs, p_objs = await _pair_records(current_store, partner, db)
    ledger = compute_ledger(_t_view(t_objs, current_store.id), _p_view(p_objs, current_store.id))
    ledger["partner_id"] = partner.id
    ledger["partner_name"] = partner.name
    return ledger


async def get_monthly_report(current_store: Store, partner_id: uuid.UUID, month: str, db: AsyncSession) -> dict:
    partner = await _get_partner(current_store, partner_id, db)
    t_objs, p_objs = await _pair_records(current_store, partner, db)
    report = compute_monthly_report(month, _t_view(t_objs, current_store.id), _p_view(p_objs, current_store.id))
    report["store_name"] = current_store.name
    report["partner_id"] = partner.id
    report["partner_name"] = partner.name
    report["transfers"] = [
        {"transfer_date": t.transfer_date,
         "direction": "outgoing" if t.from_store_id == current_store.id else "incoming",
         "items": t.items, "total": round(float(sum(i.line_total for i in t.items)), 2), "note": t.note}
        for t in t_objs if t.transfer_date.strftime("%Y-%m") == month
    ]
    return report


async def list_payments(current_store: Store, partner_id: uuid.UUID, db: AsyncSession):
    partner = await _get_partner(current_store, partner_id, db)
    result = await db.execute(
        select(SettlementPayment)
        .where(_pair_pay(current_store.id, partner.linked_store_id), SettlementPayment.is_deleted.is_(False))
        .order_by(SettlementPayment.paid_on.desc(), SettlementPayment.created_at.desc())
    )
    payments = list(result.scalars().all())
    return [
        {"id": p.id, "payer": "me" if p.from_store_id == current_store.id else "partner",
         "amount": float(p.amount), "paid_on": p.paid_on, "note": p.note,
         "created_by_label": p.created_by_label}
        for p in payments
    ]


async def record_payment(
    current_store: Store, user: User, partner_id: uuid.UUID,
    amount: float, payer: str, paid_on: date | None, note: str | None, db: AsyncSession,
) -> dict:
    partner = await _get_partner(current_store, partner_id, db)
    other = partner.linked_store_id
    from_id, to_id = (current_store.id, other) if payer == "me" else (other, current_store.id)
    payment = SettlementPayment(
        from_store_id=from_id, to_store_id=to_id, amount=amount,
        paid_on=paid_on or date.today(), note=note,
        created_by_user_id=user.id, created_by_store_id=current_store.id,
        created_by_label=_label(user, current_store),
    )
    db.add(payment)
    await db.commit()
    await db.refresh(payment)
    return {"id": payment.id, "payer": payer, "amount": float(payment.amount),
            "paid_on": payment.paid_on, "note": payment.note,
            "created_by_label": payment.created_by_label}


async def undo_payment(current_store: Store, user: User, payment_id: uuid.UUID, db: AsyncSession) -> None:
    result = await db.execute(
        select(SettlementPayment).where(
            SettlementPayment.id == payment_id,
            or_(SettlementPayment.from_store_id == current_store.id,
                SettlementPayment.to_store_id == current_store.id),
        )
    )
    payment = result.scalar_one_or_none()
    if payment is None:
        raise ValueError("Payment not found for this store.")
    if payment.is_deleted:
        raise ValueError("This payment was already removed.")
    payment.is_deleted = True
    payment.deleted_by_label = _label(user, current_store)
    payment.deleted_at = datetime.now(timezone.utc)
    await db.commit()
