"""
services/sms_service.py — SMS delivery via Twilio (Phase 21)

Safe by default: if Twilio isn't configured (no creds in .env), sending is a
DRY RUN — the message is logged, never sent. Compliance opt-out text ("Reply
STOP to unsubscribe") is appended to every message automatically.

Config (.env):
  TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER
"""

import asyncio
import logging

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

OPT_OUT_SUFFIX = " Reply STOP to unsubscribe."

_CONFIGURED = bool(
    settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_from_number
)
_client = None
if _CONFIGURED:
    try:
        from twilio.rest import Client
        _client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        logger.warning("SMS backend: Twilio (%s)", settings.twilio_from_number)
    except Exception as e:  # pragma: no cover
        logger.error("Twilio init failed, falling back to dry-run: %s", e)
        _CONFIGURED = False
else:
    logger.warning("SMS backend: DRY-RUN (Twilio not configured — messages are logged, not sent)")


def is_configured() -> bool:
    return _CONFIGURED


def build_sms_body(copy: str) -> str:
    """Trim to a safe length and always append the opt-out line (TCPA)."""
    max_body = 320 - len(OPT_OUT_SUFFIX)
    body = (copy or "").strip()
    if len(body) > max_body:
        body = body[: max_body - 1].rstrip() + "…"
    return body + OPT_OUT_SUFFIX


async def send_sms(to_number: str, body: str) -> dict:
    """
    Returns {"status": "sent"|"dry_run"|"failed", "error": str|None}.
    Never raises — the caller logs the per-recipient result.
    """
    if not _CONFIGURED:
        logger.info("[DRY-RUN SMS] → %s: %s", to_number, body)
        return {"status": "dry_run", "error": None}

    def _send():
        return _client.messages.create(
            to=to_number, from_=settings.twilio_from_number, body=body,
        )

    try:
        await asyncio.to_thread(_send)
        return {"status": "sent", "error": None}
    except Exception as e:
        logger.error("SMS to %s failed: %s", to_number, e)
        return {"status": "failed", "error": str(e)}
