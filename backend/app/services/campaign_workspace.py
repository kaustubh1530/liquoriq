"""
services/campaign_workspace.py — PHASE 23.7: the state of one campaign.

PROGRESS IS COMPUTED, NEVER STORED.

The obvious design is a row of booleans — ad_done, labels_done, sms_done — set
by whichever page finished the work. It is also wrong. Flags drift: a creative
gets deleted and the flag stays true; a label is made outside the workspace and
the flag stays false. The owner then sees a progress bar that disagrees with
his own assets, which is worse than no progress bar.

So each step reports itself by LOOKING AT THE REAL ASSET. The ad step asks the
creative table. The labels step asks label_designs. The send step asks
campaigns. There is nothing to keep in sync because there is nothing duplicated.

The one thing that IS stored is intent — status and schedule — because nothing
else records it.
"""

import logging
import uuid
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign_workspace import CampaignWorkspace

logger = logging.getLogger(__name__)

# The pipeline, in the order the owner works through it. Each step names the
# route that does the work, so the UI never hard-codes a path.
STEPS = [
    {"key": "strategy", "label": "Strategy", "route": "/ai"},
    {"key": "ad", "label": "Advertisement", "route": "/creative"},
    {"key": "labels", "label": "Shelf labels", "route": "/labels"},
    {"key": "social", "label": "Social copy", "route": None},
    {"key": "email", "label": "Email", "route": None},
    {"key": "sms", "label": "SMS", "route": None},
    {"key": "scheduled", "label": "Scheduled", "route": None},
    {"key": "roi", "label": "ROI", "route": "/intelligence"},
]


async def get_or_create(strategy_id: uuid.UUID, store_id: uuid.UUID,
                        db: AsyncSession) -> CampaignWorkspace:
    """
    The workspace for a strategy, created on first visit.

    Created lazily rather than at strategy generation: most strategies are read
    and never executed, and a table full of empty workspaces is noise in the
    campaign history the owner is meant to scan.
    """
    workspace = (await db.execute(
        select(CampaignWorkspace).where(
            CampaignWorkspace.strategy_id == strategy_id,
            CampaignWorkspace.store_id == store_id,
        )
    )).scalar_one_or_none()

    if workspace is None:
        workspace = CampaignWorkspace(store_id=store_id, strategy_id=strategy_id)
        db.add(workspace)
        await db.flush()
    return workspace


async def _has_creative(strategy_id, store_id, db) -> dict:
    try:
        from app.models.ad_creative import AdCreative
        row = (await db.execute(
            select(AdCreative)
            .where(AdCreative.strategy_id == strategy_id)
            .order_by(AdCreative.created_at.desc())
            .limit(1)
        )).scalar_one_or_none()
        return {"done": row is not None,
                "detail": ("created " + row.created_at.strftime("%d %b")) if row else "",
                "asset_id": str(row.id) if row else None}
    except Exception:  # noqa: BLE001 — an unreadable step reports "not done"
        logger.warning("Could not read the ad step", exc_info=True)
        return {"done": False, "detail": ""}


def _labels_step(linked: int, unlinked: int) -> dict:
    """
    The labels step, from two counts.

    PHASE 23.8 — this used to be the one dishonest square on the bar. Labels had
    no strategy_id, so the step could only ask "does this shop have ANY saved
    label?", and a tag made for July's clearance ticked off June's Father's Day
    campaign. The migration gave labels a campaign, so the step now asks the
    question it always meant to ask, and `weak` is gone with it.

    Labels the owner made before the migration (or outside any campaign) still
    count for something — they are mentioned, because "you have 6 labels, none
    of them on this campaign" is useful — but they never mark the step done.
    Pure, so the wording is testable without a database.
    """
    if linked:
        return {"done": True,
                "detail": f"{linked} label{'s' if linked != 1 else ''} for this campaign"}
    if unlinked:
        return {"done": False,
                "detail": f"{unlinked} saved in Label Studio, none for this campaign"}
    return {"done": False, "detail": ""}


async def _has_labels(strategy_id, store_id, db) -> dict:
    """Labels made FOR THIS CAMPAIGN — since Phase 23.8, a real signal."""
    try:
        from app.services import label_design_service as LABELS
        linked = await LABELS.count_labels(store_id, db, strategy_id)
        total = await LABELS.count_labels(store_id, db)
        return _labels_step(linked, total - linked)
    except Exception:  # noqa: BLE001 — an unreadable step reports "not done"
        logger.warning("Could not read the labels step", exc_info=True)
        return {"done": False, "detail": ""}


async def _has_send(strategy_id, store_id, db) -> dict:
    try:
        from app.models.campaign import Campaign
        rows = (await db.execute(
            select(Campaign).where(Campaign.strategy_id == strategy_id)
        )).scalars().all()
        channels = {getattr(r, "channel", None) for r in rows}
        return {"sms": "sms" in channels, "email": "email" in channels,
                "count": len(rows)}
    except Exception:  # noqa: BLE001
        return {"sms": False, "email": False, "count": 0}


def _copy_present(strategy, channel: str, overrides: dict | None) -> bool:
    """Copy counts as done when the strategy produced it or the owner wrote it."""
    if (overrides or {}).get(channel):
        return True
    field = {"social": "social_caption", "email": "email_body", "sms": "sms_copy"}[channel]
    return bool((getattr(strategy, field, "") or "").strip())


async def build_state(strategy, workspace: CampaignWorkspace,
                      store_id: uuid.UUID, db: AsyncSession) -> dict:
    """
    The whole workspace: context, progress, schedule, history.

    Everything except status and schedule is derived from assets that already
    exist, so this can never disagree with the tools that made them.
    """
    from app.services import campaign_context as CTX

    context = await CTX.build(strategy, store_id, db)
    overrides = workspace.copy_overrides or {}

    ad = await _has_creative(strategy.id, store_id, db)
    labels = await _has_labels(strategy.id, store_id, db)
    sends = await _has_send(strategy.id, store_id, db)

    done = {
        "strategy": {"done": True, "detail": "generated"},
        "ad": ad,
        "labels": labels,
        "social": {"done": _copy_present(strategy, "social", overrides),
                   "detail": "written by the strategy"},
        "email": {"done": _copy_present(strategy, "email", overrides),
                  "detail": "written by the strategy"},
        "sms": {"done": _copy_present(strategy, "sms", overrides),
                "detail": "written by the strategy"},
        "scheduled": {"done": workspace.scheduled_for is not None,
                      "detail": (workspace.scheduled_for.strftime("%a %d %b, %H:%M")
                                 if workspace.scheduled_for else "")},
        "roi": {"done": sends["count"] > 0,
                "detail": (f"{sends['count']} send(s) — measurable"
                           if sends["count"] else "runs once the campaign has")},
    }

    steps = [{**step, **done.get(step["key"], {"done": False})} for step in STEPS]
    complete = sum(1 for s in steps if s["done"])

    return {
        "workspace_id": str(workspace.id),
        "strategy_id": str(strategy.id),
        "status": workspace.status,
        "context": context,
        "steps": steps,
        "progress": {
            "complete": complete,
            "total": len(steps),
            "pct": round(complete / len(steps) * 100),
            "next": next((s for s in steps if not s["done"]), None),
        },
        "schedule": {
            "preset": workspace.schedule_preset,
            "scheduled_for": (workspace.scheduled_for.isoformat()
                              if workspace.scheduled_for else None),
            "note": workspace.schedule_note,
            "options": schedule_options(),
        },
        "copy": {
            "social": overrides.get("social") or getattr(strategy, "social_caption", ""),
            "email_subject": overrides.get("email_subject")
                             or getattr(strategy, "email_subject", ""),
            "email": overrides.get("email") or getattr(strategy, "email_body", ""),
            "sms": overrides.get("sms") or getattr(strategy, "sms_copy", ""),
            "vivino": getattr(strategy, "vivino_listing", ""),
            "edited": sorted(overrides.keys()),
        },
        "timeline": {
            "created": workspace.created_at.isoformat() if workspace.created_at else None,
            "updated": workspace.updated_at.isoformat() if workspace.updated_at else None,
            "launched": workspace.launched_at.isoformat() if workspace.launched_at else None,
        },
        "coach": _coach_line(context, steps),
    }


def _coach_line(context: dict, steps: list[dict]) -> str:
    """
    One sentence at the top of the workspace.

    Assembled from the strategy's own words — NOT a GPT call. This slot is on
    screen before anything else finishes loading, and a model call here would
    put a spinner in it on every visit for prose that changes only when the
    strategy does.
    """
    summary = context.get("summary", {})
    outstanding = [s["label"].lower() for s in steps if not s["done"]]

    parts = []
    if summary.get("expected_outcome"):
        parts.append(summary["expected_outcome"].rstrip("."))
    if summary.get("occasion"):
        parts.append(f"built around {summary['occasion']}")

    lead = ". ".join(p for p in parts if p)
    if outstanding:
        remaining = ", ".join(outstanding[:2])
        lead = f"{lead}. Still to do: {remaining}." if lead \
            else f"Still to do: {remaining}."
    return lead.strip()


def schedule_options(today: date | None = None) -> list[dict]:
    """
    The windows an owner actually thinks in.

    Resolved to real datetimes here rather than in the browser, so a schedule
    means the same thing whichever device set it — and so a worker reading
    these rows later never has to interpret "Friday evening".
    """
    today = today or date.today()

    def at(day: date, hour: int) -> str:
        return datetime.combine(day, time(hour, 0), tzinfo=timezone.utc).isoformat()

    friday = today + timedelta(days=(4 - today.weekday()) % 7 or 7)
    saturday = today + timedelta(days=(5 - today.weekday()) % 7 or 7)

    return [
        {"preset": "immediately", "label": "As soon as it's ready",
         "when": at(today, 9), "why": "no waiting"},
        {"preset": "tomorrow", "label": "Tomorrow morning",
         "when": at(today + timedelta(days=1), 9), "why": "time to check it over"},
        {"preset": "friday_evening", "label": "Friday evening",
         "when": at(friday, 17),
         "why": "catches the pre-weekend shop, the busiest window of the week"},
        {"preset": "saturday_morning", "label": "Saturday morning",
         "when": at(saturday, 10), "why": "weekend planners"},
        {"preset": "custom", "label": "Pick a date and time", "when": None,
         "why": "for a holiday or a delivery date"},
    ]


def resolve_schedule(preset: str, custom: datetime | None,
                     today: date | None = None) -> datetime | None:
    """Turn a preset into a datetime. `custom` wins when supplied."""
    if custom is not None:
        return custom
    for option in schedule_options(today):
        if option["preset"] == preset and option["when"]:
            return datetime.fromisoformat(option["when"])
    return None
