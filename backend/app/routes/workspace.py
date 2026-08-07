"""
routes/workspace.py — PHASE 23.7: the Campaign Workspace API.

GET   /workspace/{strategy_id}          the whole workspace, created on first visit
PATCH /workspace/{strategy_id}/schedule choose when it goes out (preparation only)
PATCH /workspace/{strategy_id}/status   move it through the lifecycle
PATCH /workspace/{strategy_id}/copy     save an edit to generated copy
GET   /workspace                        campaign history
GET   /workspace/{strategy_id}/package  everything, zipped (Phase 23.8)

NO NEW CALCULATIONS AND NO GPT CALLS. Everything is assembled from the
CampaignContext plus assets that already exist.
"""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status as http
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.ai_strategy_report import AIStrategyReport
from app.models.campaign_workspace import (SCHEDULE_PRESETS, STATUSES,
                                           CampaignWorkspace)
from app.models.store import Store
from app.routes.stores import get_current_store
from app.services import campaign_package as PKG
from app.services import campaign_workspace as WS

router = APIRouter()


async def _strategy(strategy_id: uuid.UUID, store: Store,
                    db: AsyncSession) -> AIStrategyReport:
    row = (await db.execute(
        select(AIStrategyReport).where(
            AIStrategyReport.id == strategy_id,
            AIStrategyReport.store_id == store.id,
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(http.HTTP_404_NOT_FOUND,
                            detail="That campaign does not exist.")
    return row


@router.get("", summary="Campaign history")
async def history(
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Every campaign the owner has started work on, newest first."""
    rows = (await db.execute(
        select(CampaignWorkspace, AIStrategyReport)
        .join(AIStrategyReport, AIStrategyReport.id == CampaignWorkspace.strategy_id)
        .where(CampaignWorkspace.store_id == current_store.id)
        .order_by(CampaignWorkspace.updated_at.desc())
        .limit(50)
    )).all()

    return {"campaigns": [
        {
            "workspace_id": str(w.id),
            "strategy_id": str(w.strategy_id),
            "title": s.strategy_title,
            "occasion": s.occasion,
            "status": w.status,
            "scheduled_for": w.scheduled_for.isoformat() if w.scheduled_for else None,
            "updated_at": w.updated_at.isoformat() if w.updated_at else None,
        }
        for w, s in rows
    ]}


@router.get("/{strategy_id}", summary="The whole campaign workspace")
async def workspace(
    strategy_id: uuid.UUID,
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Context, progress, schedule, copy and history for one campaign.

    Created on first visit — most strategies are read and never executed, and
    a table of empty workspaces would clutter the history the owner scans.
    """
    strategy = await _strategy(strategy_id, current_store, db)
    ws = await WS.get_or_create(strategy_id, current_store.id, db)
    state = await WS.build_state(strategy, ws, current_store.id, db)
    await db.commit()
    return state


@router.get("/{strategy_id}/package", response_class=Response,
            summary="Download the whole campaign as a ZIP")
async def package(
    strategy_id: uuid.UUID,
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    The ad, the labels, every piece of copy and a summary PDF, in one folder.

    The ZIP is built from the SAME state object this page renders — see
    services/campaign_package.py. It is a second rendering, never a second
    opinion: an owner who found a different SMS in the ZIP than on the screen
    would have no way to tell which one he had actually sent.

    An incomplete campaign still packages. What is missing is named in the
    README rather than refused, because withholding a man's own work until he
    finishes it is not a feature.
    """
    strategy = await _strategy(strategy_id, current_store, db)
    ws = await WS.get_or_create(strategy_id, current_store.id, db)
    state = await WS.build_state(strategy, ws, current_store.id, db)
    await db.commit()

    assets = await PKG.collect_assets(strategy_id, current_store.id, db)
    filename, blob = PKG.build(state, current_store.name or "Your store", assets)

    return Response(
        content=blob, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


class ScheduleIn(BaseModel):
    preset: str = Field(description=f"One of: {', '.join(SCHEDULE_PRESETS)}")
    scheduled_for: datetime | None = Field(default=None,
                                           description="Required when preset=custom")
    note: str | None = Field(default=None, max_length=500)


@router.patch("/{strategy_id}/schedule", summary="Choose when the campaign goes out")
async def set_schedule(
    strategy_id: uuid.UUID,
    body: ScheduleIn,
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    PREPARATION, NOT EXECUTION.

    This records the owner's intent. Nothing reads these rows to send anything
    yet — a worker that does is a later phase. Saying so plainly here matters:
    an owner who thinks he has scheduled an SMS that never sends has been
    failed by the product in the worst possible way.
    """
    if body.preset not in SCHEDULE_PRESETS:
        raise HTTPException(http.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"Unknown schedule option: {body.preset}")
    if body.preset == "custom" and body.scheduled_for is None:
        raise HTTPException(http.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="A custom schedule needs a date and time.")

    await _strategy(strategy_id, current_store, db)
    ws = await WS.get_or_create(strategy_id, current_store.id, db)

    ws.schedule_preset = body.preset
    ws.scheduled_for = WS.resolve_schedule(body.preset, body.scheduled_for)
    ws.schedule_note = body.note
    if ws.status == "draft":
        ws.status = "scheduled"
    await db.commit()

    return {
        "preset": ws.schedule_preset,
        "scheduled_for": ws.scheduled_for.isoformat() if ws.scheduled_for else None,
        "status": ws.status,
        "note": "Saved. Sending is not automated yet — this records when you "
                "intend to launch.",
    }


class StatusIn(BaseModel):
    status: str = Field(description=f"One of: {', '.join(STATUSES)}")


@router.patch("/{strategy_id}/status", summary="Move the campaign along")
async def set_status(
    strategy_id: uuid.UUID,
    body: StatusIn,
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    if body.status not in STATUSES:
        raise HTTPException(http.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"Unknown status: {body.status}")

    await _strategy(strategy_id, current_store, db)
    ws = await WS.get_or_create(strategy_id, current_store.id, db)
    ws.status = body.status
    if body.status == "launched" and ws.launched_at is None:
        ws.launched_at = datetime.now(tz=ws.created_at.tzinfo)
    await db.commit()
    return {"status": ws.status}


class CopyIn(BaseModel):
    channel: str = Field(description="social | email | email_subject | sms")
    text: str = Field(max_length=5000)


@router.patch("/{strategy_id}/copy", summary="Save an edit to generated copy")
async def set_copy(
    strategy_id: uuid.UUID,
    body: CopyIn,
    current_store: Annotated[Store, Depends(get_current_store)],
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Edits are stored as OVERRIDES, not by overwriting the strategy.

    The original AI output stays auditable, and a regretted edit is undone by
    clearing one key rather than by regenerating the whole campaign.
    """
    allowed = {"social", "email", "email_subject", "sms"}
    if body.channel not in allowed:
        raise HTTPException(http.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"Channel must be one of: {', '.join(sorted(allowed))}")

    await _strategy(strategy_id, current_store, db)
    ws = await WS.get_or_create(strategy_id, current_store.id, db)
    overrides = dict(ws.copy_overrides or {})
    if body.text.strip():
        overrides[body.channel] = body.text
    else:
        overrides.pop(body.channel, None)   # empty = revert to the AI original
    ws.copy_overrides = overrides
    await db.commit()
    return {"channel": body.channel, "edited": sorted(overrides.keys())}
