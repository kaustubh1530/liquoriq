"""
routes/transfers.py — Shared exchange ledger endpoints (Phase 14, shared model)

Both linked stores see the same records. Staff and owners can record and undo
transfers (data entry); only owners record/undo settlement payments (money).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.store import Store
from app.models.user import User
from app.routes.auth import get_current_user
from app.routes.stores import get_current_store
from app.schemas.transfer import (
    LedgerResponse, MonthlyReportResponse, PartnerCreate, PartnerResponse,
    PaymentCreate, PaymentResponse, TransferCreate, TransferResponse,
)
from app.services.transfer_service import (
    create_partner, create_transfer, deactivate_partner, get_ledger,
    get_monthly_report, list_partners, list_payments, list_transfers,
    record_payment, undo_payment, undo_transfer,
)

router = APIRouter()


# ─── Partners ─────────────────────────────────────────────────────────────────

@router.post("/partners", response_model=PartnerResponse,
             status_code=status.HTTP_201_CREATED,
             summary="Add an exchange partner by their exchange code (mandatory)")
async def add_partner(
    body: PartnerCreate,
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
):
    try:
        p = await create_partner(current_store, body.code, body.name, db)
        p["mutual"] = False
        return p
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.get("/partners", response_model=list[PartnerResponse],
            summary="List exchange partners")
async def partners(
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
):
    return await list_partners(current_store, db)


@router.delete("/partners/{partner_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Remove an exchange partner")
async def remove_partner(
    partner_id: uuid.UUID,
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
):
    try:
        await deactivate_partner(current_store, partner_id, db)
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))


# ─── Transfers ────────────────────────────────────────────────────────────────

@router.post("", response_model=TransferResponse, status_code=status.HTTP_201_CREATED,
             summary="Record an exchange (either direction)")
async def create(
    body: TransferCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
):
    try:
        return await create_transfer(
            current_store=current_store, user=current_user,
            partner_id=body.partner_id, direction=body.direction,
            items=[i.model_dump() for i in body.items],
            transfer_date=body.transfer_date, note=body.note, db=db,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.get("", response_model=list[TransferResponse],
            summary="Shared exchange history for a partner")
async def history(
    partner_id: uuid.UUID,
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
):
    try:
        return await list_transfers(current_store, partner_id, db)
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{transfer_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Undo an exchange record (audited)")
async def undo(
    transfer_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
):
    try:
        await undo_transfer(current_store, current_user, transfer_id, db)
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))


# ─── Ledger / report / payments ───────────────────────────────────────────────

@router.get("/ledger/{partner_id}", response_model=LedgerResponse,
            summary="Balance + monthly statement with a partner")
async def ledger(
    partner_id: uuid.UUID,
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
):
    try:
        return await get_ledger(current_store, partner_id, db)
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/payments/{partner_id}", response_model=list[PaymentResponse],
            summary="Settlement payments with a partner")
async def payments(
    partner_id: uuid.UUID,
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
):
    try:
        return await list_payments(current_store, partner_id, db)
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/settle/{partner_id}", response_model=PaymentResponse,
             status_code=status.HTTP_201_CREATED,
             summary="Record a settle-up payment (owner only)")
async def settle(
    partner_id: uuid.UUID,
    body: PaymentCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != "owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Only the owner can record payments.")
    try:
        return await record_payment(
            current_store=current_store, user=current_user, partner_id=partner_id,
            amount=body.amount, payer=body.payer, paid_on=body.paid_on, note=body.note, db=db,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.delete("/payments/{payment_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Undo a settlement payment (owner only, audited)")
async def undo_settle(
    payment_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != "owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Only the owner can undo payments.")
    try:
        await undo_payment(current_store, current_user, payment_id, db)
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/report/{partner_id}", response_model=MonthlyReportResponse,
            summary="End-of-month statement (add ?format=csv to download)")
async def monthly_report(
    partner_id: uuid.UUID,
    month: str,
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
    format: str = "json",
):
    import re as _re
    if not _re.fullmatch(r"\d{4}-\d{2}", month):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="month must look like 2026-07")
    try:
        report = await get_monthly_report(current_store, partner_id, month, db)
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))

    if format != "csv":
        return report

    import csv
    import io

    from fastapi.responses import Response

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([f"Exchange statement {report['month']}",
                f"{report['store_name']} <-> {report['partner_name']}"])
    w.writerow([])
    w.writerow(["Opening balance (carry-forward)", report["opening_balance"]])
    w.writerow(["Sent this month", report["month_sent"]])
    w.writerow(["Received this month", report["month_received"]])
    w.writerow(["Payments made", report["payments_out"]])
    w.writerow(["Payments received", report["payments_in"]])
    w.writerow(["CLOSING BALANCE", report["closing_balance"]])
    w.writerow([])
    w.writerow(["Date", "Direction", "Product", "Qty", "Unit cost", "Line total", "Note"])
    for t in report["transfers"]:
        for i, item in enumerate(t["items"]):
            w.writerow([
                t["transfer_date"] if i == 0 else "",
                t["direction"] if i == 0 else "",
                item.product_name, float(item.quantity),
                float(item.unit_cost), float(item.line_total),
                (t["note"] or "") if i == 0 else "",
            ])

    filename = f"exchange_{report['month']}_{report['partner_name'].replace(' ', '_')}.csv"
    return Response(content=buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})
