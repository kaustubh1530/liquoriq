"""
services/customer_service.py — Customer ingestion + segmentation (Phase 19)

Every operation is scoped to store_id (strict store isolation). Ingest is
idempotent per customer via dedup_key. RFM/segment is DERIVED at read time from
the stored aggregates (self-correcting), using services/rfm.py.
"""

import uuid
from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer, CustomerPurchase
from app.services import rfm
from app.services.parsers.customer_parser import dedup_key


async def ingest_customers(store_id: uuid.UUID, parsed: list[dict], db: AsyncSession) -> dict:
    """
    Upsert parsed customers into this store. Snapshot semantics: a customer's
    aggregates are set to the report's values (re-upload is idempotent). Consent
    is OR-merged (never silently revoked by a report that omits it).
    Transaction rows (if any) are appended.
    """
    created = updated = 0
    for rec in parsed:
        key = rec["dedup_key"]
        result = await db.execute(
            select(Customer).where(Customer.store_id == store_id, Customer.dedup_key == key)
        )
        cust = result.scalar_one_or_none()

        if cust is None:
            cust = Customer(store_id=store_id, dedup_key=key)
            db.add(cust)
            created += 1
        else:
            updated += 1

        cust.name = rec.get("name") or cust.name
        cust.email = rec.get("email") or cust.email
        cust.phone = rec.get("phone") or cust.phone
        cust.total_spent = rec.get("total_spent") or 0
        cust.purchase_count = rec.get("purchase_count") or 0
        cust.last_purchase_date = rec.get("last_purchase_date") or cust.last_purchase_date
        cust.first_purchase_date = rec.get("first_purchase_date") or cust.first_purchase_date
        cust.sms_opt_in = bool(cust.sms_opt_in) or bool(rec.get("sms_opt_in"))
        cust.email_opt_in = bool(cust.email_opt_in) or bool(rec.get("email_opt_in"))

        await db.flush()  # assign cust.id for purchases

        for t in rec.get("transactions", []):
            db.add(CustomerPurchase(
                store_id=store_id, customer_id=cust.id,
                purchase_date=t.get("purchase_date"),
                amount=t.get("amount") or 0,
                product_name=t.get("product_name"),
            ))

    await db.commit()
    return {"created": created, "updated": updated, "total": created + updated}


async def create_customer(store_id: uuid.UUID, data: dict, db: AsyncSession) -> dict:
    """
    Manually add (or update) a single customer. Uses the same idempotent
    dedup-key upsert as file ingestion. Requires at least a name, email, or phone.
    """
    key = dedup_key(data.get("name"), data.get("email"), data.get("phone"))
    if not key:
        raise ValueError("Enter at least a name, email, or phone.")

    last = data.get("last_purchase_date")
    rec = {
        "dedup_key": key,
        "name": data.get("name"), "email": data.get("email"), "phone": data.get("phone"),
        "total_spent": float(data.get("total_spent") or 0),
        "purchase_count": int(data.get("purchase_count") or 0),
        "last_purchase_date": last,
        "first_purchase_date": data.get("first_purchase_date") or last,
        "sms_opt_in": bool(data.get("sms_opt_in")),
        "email_opt_in": bool(data.get("email_opt_in")),
        "transactions": [],
    }
    await ingest_customers(store_id, [rec], db)

    result = await db.execute(
        select(Customer).where(Customer.store_id == store_id, Customer.dedup_key == key)
    )
    c = result.scalar_one()
    d = _to_dict(c)
    d.update(rfm.compute_rfm(d, date.today()))
    d["id"] = str(d["id"])
    d["last_purchase_date"] = d["last_purchase_date"].isoformat() if d["last_purchase_date"] else None
    d["first_purchase_date"] = d["first_purchase_date"].isoformat() if d["first_purchase_date"] else None
    return d


def _to_dict(c: Customer) -> dict:
    return {
        "id": c.id, "name": c.name, "email": c.email, "phone": c.phone,
        "total_spent": float(c.total_spent or 0),
        "purchase_count": int(c.purchase_count or 0),
        "last_purchase_date": c.last_purchase_date,
        "first_purchase_date": c.first_purchase_date,
        "sms_opt_in": bool(c.sms_opt_in), "email_opt_in": bool(c.email_opt_in),
    }


async def list_customers(
    store_id: uuid.UUID, db: AsyncSession,
    segment: str | None = None, search: str | None = None, limit: int = 500,
) -> list[dict]:
    query = select(Customer).where(Customer.store_id == store_id)
    if search:
        like = f"%{search.strip()}%"
        query = query.where(or_(
            Customer.name.ilike(like), Customer.email.ilike(like), Customer.phone.ilike(like),
        ))
    query = query.order_by(Customer.total_spent.desc()).limit(limit)
    rows = (await db.execute(query)).scalars().all()

    today = date.today()
    out = []
    for c in rows:
        d = _to_dict(c)
        d.update(rfm.compute_rfm(d, today))
        if segment and d["segment"] != segment:
            continue
        # dates → iso for JSON
        d["last_purchase_date"] = d["last_purchase_date"].isoformat() if d["last_purchase_date"] else None
        d["first_purchase_date"] = d["first_purchase_date"].isoformat() if d["first_purchase_date"] else None
        d["id"] = str(d["id"])
        out.append(d)
    return out


async def get_segment_audience(store_id: uuid.UUID, segment: str, db: AsyncSession) -> dict:
    """
    Aggregated stats for one RFM segment in this store (store-isolated).
    Returns ONLY aggregates + warnings + the segment playbook — NO customer PII.
    Raises ValueError if the segment name is invalid.
    """
    if segment not in rfm.SEGMENTS:
        raise ValueError(f"Unknown segment '{segment}'. Valid: {', '.join(rfm.SEGMENTS)}")

    rows = (await db.execute(
        select(Customer).where(Customer.store_id == store_id)
    )).scalars().all()
    today = date.today()

    matching = []
    for c in rows:
        d = _to_dict(c)
        if rfm.compute_rfm(d, today)["segment"] == segment:
            matching.append(d)

    stats = rfm.segment_stats(matching)
    return {
        "segment": segment,
        **stats,
        "warnings": rfm.audience_warnings(stats),
        "recommendation": rfm.SEGMENT_RECOMMENDATIONS[segment],
        "playbook": rfm.SEGMENT_PLAYBOOK[segment],
    }


async def get_recipients(
    store_id: uuid.UUID, channel: str, db: AsyncSession, segment: str | None = None,
) -> list[dict]:
    """
    Customers eligible to receive a `channel` message: consented (opt_in),
    NOT suppressed (opted_out), with a usable address, in `segment` if given.
    Returns [{customer_id, to}]. Store-isolated.
    """
    query = select(Customer).where(Customer.store_id == store_id)
    if channel == "sms":
        query = query.where(
            Customer.sms_opt_in.is_(True), Customer.sms_opted_out.is_(False),
            Customer.phone.isnot(None),
        )
    elif channel == "email":
        query = query.where(
            Customer.email_opt_in.is_(True), Customer.email_opted_out.is_(False),
            Customer.email.isnot(None),
        )
    else:
        raise ValueError("channel must be 'sms' or 'email'")

    rows = (await db.execute(query)).scalars().all()
    today = date.today()
    out = []
    for c in rows:
        if segment:
            d = _to_dict(c)
            if rfm.compute_rfm(d, today)["segment"] != segment:
                continue
        addr = c.phone if channel == "sms" else c.email
        if addr and addr.strip():
            out.append({"customer_id": c.id, "to": addr.strip()})
    return out


async def opt_out(store_id: uuid.UUID, customer_id: uuid.UUID, channel: str, db: AsyncSession) -> None:
    """Suppress a customer from a channel (survives re-uploads)."""
    result = await db.execute(
        select(Customer).where(Customer.id == customer_id, Customer.store_id == store_id)
    )
    c = result.scalar_one_or_none()
    if c is None:
        raise ValueError("Customer not found.")
    if channel == "sms":
        c.sms_opted_out = True
        c.sms_opt_in = False
    elif channel == "email":
        c.email_opted_out = True
        c.email_opt_in = False
    else:
        raise ValueError("channel must be 'sms' or 'email'")
    await db.commit()


async def segment_summary(store_id: uuid.UUID, db: AsyncSession) -> dict:
    rows = (await db.execute(
        select(Customer).where(Customer.store_id == store_id)
    )).scalars().all()
    customers = [_to_dict(c) for c in rows]
    today = date.today()

    total_customers = len(customers)
    total_value = round(sum(c["total_spent"] for c in customers), 2)
    opted_sms = sum(1 for c in customers if c["sms_opt_in"])
    opted_email = sum(1 for c in customers if c["email_opt_in"])

    return {
        "total_customers": total_customers,
        "total_value": total_value,
        "sms_opted_in": opted_sms,
        "email_opted_in": opted_email,
        "segments": rfm.summarize(customers, today),
    }
