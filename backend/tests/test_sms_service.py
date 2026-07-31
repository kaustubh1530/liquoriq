"""tests/test_sms_service.py — SMS body building + dry-run safety (Phase 21)"""

import asyncio

from app.services import sms_service


def test_opt_out_line_always_appended():
    body = sms_service.build_sms_body("Labor Day sale — 20% off tequila!")
    assert body.endswith(sms_service.OPT_OUT_SUFFIX)
    assert "20% off tequila" in body


def test_long_copy_is_truncated_and_keeps_opt_out():
    body = sms_service.build_sms_body("X" * 1000)
    assert len(body) <= 320
    assert body.endswith(sms_service.OPT_OUT_SUFFIX)


def test_dry_run_when_unconfigured_never_raises():
    # In the test env Twilio isn't configured → send_sms returns dry_run, no send.
    res = asyncio.get_event_loop().run_until_complete(
        sms_service.send_sms("+12025550100", "hi Reply STOP to unsubscribe.")
    )
    assert res["status"] in ("dry_run", "sent")   # dry_run unless creds present
    assert res["error"] is None
