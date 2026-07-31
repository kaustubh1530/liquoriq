"""
services/campaign_delivery_service.py — Send a strategy's copy to customers (Phase 21)

Compliance-first delivery:
  - Recipients = ONLY opted-in, non-suppressed customers with a usable address,
    optionally filtered to the strategy's target segment.
  - SMS uses the strategy's sms_copy + an auto opt-out line; email uses the
    strategy's email_subject/email_body.
  - Every recipient is logged (MessageLog) with sent/failed/dry_run status.
  - Nothing sends unless the caller confirms; SMS is a DRY RUN unless Twilio is
    configured. No message is ever sent to a suppressed customer.
"""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_strategy_report import AIStrategyReport
from app.models.campaign import Campaign, MessageLog
from app.services import sms_service
from app.services.customer_service import get_recipients
from app.services.email_service import send_html_email

logger = logging.getLogger(__name__)


async def _load_strategy(strategy_id: uuid.UUID, store_id: uuid.UUID, db: AsyncSession) -> AIStrategyReport:
    result = await db.execute(
        select(AIStrategyReport).where(
            AIStrategyReport.id == strategy_id, AIStrategyReport.store_id == store_id
        )
    )
    strategy = result.scalar_one_or_none()
    if strategy is None:
        raise ValueError("Strategy not found")
    return strategy


async def preview_campaign(
    strategy_id: uuid.UUID, store_id: uuid.UUID, channel: str, db: AsyncSession,
) -> dict:
    """Recipient count + a sample of what will be sent + warnings. No sending."""
    strategy = await _load_strategy(strategy_id, store_id, db)
    segment = strategy.target_segment
    recipients = await get_recipients(store_id, channel, db, segment=segment)

    if channel == "sms":
        sample = sms_service.build_sms_body(strategy.sms_copy)
    else:
        sample = f"Subject: {strategy.email_subject}\n\n{strategy.email_body}"

    warnings = []
    if len(recipients) == 0:
        warnings.append(
            f"No {'phone' if channel == 'sms' else 'email'} recipients are opted in"
            + (f" in the '{segment}' segment." if segment else ".")
        )
    if channel == "sms" and not sms_service.is_configured():
        warnings.append("Twilio is not configured — this will be a DRY RUN (nothing is sent).")

    return {
        "channel": channel,
        "target_segment": segment,
        "recipient_count": len(recipients),
        "sample_message": sample,
        "live": (channel == "email") or sms_service.is_configured(),
        "warnings": warnings,
    }


def _email_html(strategy: AIStrategyReport, store_name: str) -> str:
    body = (strategy.email_body or "").replace("\n", "<br>")
    return f"""\
<div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;color:#222">
  <h2 style="color:#e8a020">{strategy.email_subject}</h2>
  <p>{body}</p>
  <p style="margin-top:20px"><b>{strategy.recommended_offer}</b></p>
  <hr style="border:none;border-top:1px solid #eee;margin:24px 0">
  <p style="font-size:12px;color:#999">
    You're receiving this because you opted in to updates from {store_name}.
    To stop these emails, reply with "unsubscribe".
  </p>
</div>"""


async def send_campaign(
    strategy_id: uuid.UUID, store_id: uuid.UUID, user_id: uuid.UUID | None,
    channel: str, db: AsyncSession, store_name: str = "",
) -> dict:
    """Send to all eligible recipients, log each, return a summary."""
    strategy = await _load_strategy(strategy_id, store_id, db)
    segment = strategy.target_segment
    recipients = await get_recipients(store_id, channel, db, segment=segment)

    if not recipients:
        raise ValueError("No opted-in recipients for this channel/segment.")

    campaign = Campaign(
        store_id=store_id, strategy_id=strategy_id, channel=channel,
        target_segment=segment, status="sent", recipients_total=len(recipients),
        created_by_user_id=user_id,
    )
    db.add(campaign)
    await db.flush()

    sent = failed = skipped = 0
    sms_body = sms_service.build_sms_body(strategy.sms_copy) if channel == "sms" else None
    html = _email_html(strategy, store_name) if channel == "email" else None

    for r in recipients:
        status, error = "sent", None
        if channel == "sms":
            res = await sms_service.send_sms(r["to"], sms_body)
            status, error = res["status"], res["error"]
        else:
            try:
                await send_html_email(r["to"], strategy.email_subject, html)
            except Exception as e:
                status, error = "failed", str(e)

        if status in ("sent", "dry_run"):
            sent += 1
        elif status == "failed":
            failed += 1
        else:
            skipped += 1

        db.add(MessageLog(
            store_id=store_id, campaign_id=campaign.id, customer_id=r["customer_id"],
            channel=channel, to_address=r["to"], status=status, error=error,
        ))

    campaign.sent_count = sent
    campaign.failed_count = failed
    campaign.skipped_count = skipped
    if channel == "sms" and not sms_service.is_configured():
        campaign.status = "dry_run"
    elif failed and not sent:
        campaign.status = "failed"
    elif failed:
        campaign.status = "partial"
    else:
        campaign.status = "sent"

    await db.commit()
    await db.refresh(campaign)
    logger.info("Campaign %s: %d sent, %d failed (%s)", campaign.id, sent, failed, campaign.status)

    return {
        "campaign_id": str(campaign.id),
        "channel": channel,
        "status": campaign.status,
        "recipients_total": campaign.recipients_total,
        "sent_count": sent, "failed_count": failed, "skipped_count": skipped,
        "live": (channel == "email") or sms_service.is_configured(),
    }


async def list_campaigns(store_id: uuid.UUID, db: AsyncSession, limit: int = 50) -> list[dict]:
    rows = (await db.execute(
        select(Campaign).where(Campaign.store_id == store_id)
        .order_by(Campaign.created_at.desc()).limit(limit)
    )).scalars().all()
    return [
        {
            "id": str(c.id), "channel": c.channel, "target_segment": c.target_segment,
            "status": c.status, "recipients_total": c.recipients_total,
            "sent_count": c.sent_count, "failed_count": c.failed_count,
            "created_at": c.created_at.isoformat(),
        }
        for c in rows
    ]
