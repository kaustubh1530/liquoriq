"""
tests/test_transfer_ledger.py — Pure exchange-ledger math (Phase 14, partner model)

Semantics: balance > 0 → OUR store owes the partner; < 0 → they owe us.
Money math must be perfect — the pilot moves ~$80-90k/month per store.
"""

from datetime import date

from app.services.transfer_service import compute_ledger, compute_monthly_report


def t(direction, day, total):
    return {"direction": direction, "transfer_date": day, "total": total}


def p(payer, amount, day):
    return {"payer": payer, "amount": amount, "paid_on": day}


# ─── Running balance ──────────────────────────────────────────────────────────

def test_balance_when_we_received_more():
    ledger = compute_ledger(
        [t("incoming", date(2026, 7, 3), 500.0), t("outgoing", date(2026, 7, 10), 200.0)], []
    )
    assert ledger["balance"] == 300.0        # we owe 300
    assert ledger["sent_total"] == 200.0
    assert ledger["received_total"] == 500.0


def test_our_payment_reduces_our_debt():
    ledger = compute_ledger([t("incoming", date(2026, 7, 3), 500.0)], [p("me", 500.0, date(2026, 7, 20))])
    assert ledger["balance"] == 0.0


def test_partner_payment_reduces_their_debt():
    # We sent $100 → they owe us 100 (balance −100). They pay 50 → −50.
    ledger = compute_ledger([t("outgoing", date(2026, 7, 1), 100.0)], [p("partner", 50.0, date(2026, 7, 9))])
    assert ledger["balance"] == -50.0


def test_monthly_breakdown_newest_first():
    ledger = compute_ledger(
        [t("incoming", date(2026, 6, 15), 300.0), t("outgoing", date(2026, 7, 2), 100.0)], []
    )
    assert ledger["balance"] == 200.0
    assert ledger["months"][0]["month"] == "2026-07"
    months = {m["month"]: m for m in ledger["months"]}
    assert months["2026-06"]["net"] == 300.0
    assert months["2026-07"]["net"] == -100.0


def test_empty_ledger():
    ledger = compute_ledger([], [])
    assert ledger["balance"] == 0.0
    assert ledger["months"] == []


# ─── Monthly report (opening/closing carry-forward) ───────────────────────────

def test_monthly_report_carry_forward():
    transfers = [
        t("incoming", date(2026, 6, 10), 300.0),
        t("outgoing", date(2026, 7, 5), 100.0),
        t("incoming", date(2026, 7, 20), 250.0),
    ]
    payments = [p("me", 200.0, date(2026, 7, 15))]

    july = compute_monthly_report("2026-07", transfers, payments)
    assert july["opening_balance"] == 300.0
    assert july["month_sent"] == 100.0
    assert july["month_received"] == 250.0
    assert july["month_net"] == 150.0
    assert july["payments_out"] == 200.0
    assert july["closing_balance"] == 250.0   # 300 + 150 − 200


def test_closing_matches_next_opening():
    transfers = [
        t("incoming", date(2026, 6, 10), 500.0),
        t("outgoing", date(2026, 7, 5), 200.0),
    ]
    june = compute_monthly_report("2026-06", transfers, [])
    july = compute_monthly_report("2026-07", transfers, [])
    # The invariant the whole family workflow relies on:
    assert july["opening_balance"] == june["closing_balance"]


def test_report_empty_month_keeps_balance():
    r = compute_monthly_report("2026-08", [t("incoming", date(2026, 6, 1), 100.0)], [])
    assert r["opening_balance"] == 100.0
    assert r["month_net"] == 0.0
    assert r["closing_balance"] == 100.0


def test_big_month_realistic_volume():
    # ~$85k exchanged in a month, both directions + partial settlement
    transfers = (
        [t("outgoing", date(2026, 7, d), 1500.0) for d in range(1, 29)]      # 42,000 sent
        + [t("incoming", date(2026, 7, d), 1550.0) for d in range(1, 29)]    # 43,400 received
    )
    payments = [p("me", 1000.0, date(2026, 7, 30))]
    r = compute_monthly_report("2026-07", transfers, payments)
    assert r["month_sent"] == 42000.0
    assert r["month_received"] == 43400.0
    assert r["closing_balance"] == 400.0      # 0 + 1400 − 1000
