"""
routes/reports.py — Manual report trigger endpoints

POST /reports/send-weekly        — send report for the logged-in store (test)
POST /reports/send-weekly-all    — send to ALL stores (admin use only)

These exist so you can test email delivery without waiting until Monday.
In production, the scheduler calls send_all_weekly_reports() automatically.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.store import Store
from app.routes.stores import get_current_store
from app.services.report_service import (
    send_weekly_report_for_store,
    send_all_weekly_reports,
)

router = APIRouter()


@router.post(
    "/send-weekly",
    status_code=status.HTTP_200_OK,
    summary="Send weekly growth report to the logged-in store owner (test trigger)",
    description=(
        "Immediately generates and emails the weekly report for your store. "
        "Use this to test email delivery without waiting for Monday's schedule. "
        "Requires SMTP credentials in .env."
    ),
)
async def trigger_weekly_report(
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await send_weekly_report_for_store(
        store_id=current_store.id,
        db=db,
    )
    if result.get("status") == "failed":
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=result.get("error", "Report generation failed"),
        )
    return result


@router.post(
    "/send-weekly-all",
    status_code=status.HTTP_200_OK,
    summary="Send weekly reports to ALL stores (same as Monday scheduler)",
    description="Admin endpoint — triggers the full weekly report run for every active store.",
)
async def trigger_all_weekly_reports() -> dict:
    results = await send_all_weekly_reports()
    sent   = sum(1 for r in results if r.get("status") == "sent")
    failed = sum(1 for r in results if r.get("status") == "failed")
    return {
        "total":   len(results),
        "sent":    sent,
        "failed":  failed,
        "results": results,
    }
