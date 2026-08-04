"""
tests/test_bi_engine_adapters.py — PHASE 22: the seams between modules

The BI engine's pure logic was covered by 300+ tests and still shipped a 500,
because the bug was never in the logic. It was at the SEAM: engine._segments
read rfm.summarize()'s output as a mapping when it returns a list, and
engine._campaigns read "revenue_lift" when the key is "total_revenue_lift".

Neither module was wrong on its own, so neither module's tests could catch it.
These tests assert the CONTRACT between them, using the real producer's output
rather than a hand-written fixture — a fixture would just re-encode the same
wrong assumption and pass while production burns.

The second lesson encoded here: an optional feature must never take the
dashboard down. Every adapter is expected to degrade to empty, not raise.
"""

import asyncio
from datetime import date

import pytest

from app.services import rfm
from app.services.bi import engine as ENG


_LOOP = asyncio.new_event_loop()


def _run(coro):
    """
    Run one coroutine on a loop this module owns.

    Neither obvious option works here. asyncio.run() creates a loop and then
    CLOSES it, which breaks test_sms_service — that suite shares the
    process-wide loop. asyncio.get_event_loop() doesn't close anything but is
    deprecated when no loop is running, and warns. Owning a private loop avoids
    both, and keeps this file independent of test ordering.
    """
    return _LOOP.run_until_complete(coro)


CUSTOMERS = [
    {"name": "Lapsed A", "total_spent": 300.0, "purchase_count": 4,
     "last_purchase_date": date(2025, 9, 1)},
    {"name": "Lapsed B", "total_spent": 100.0, "purchase_count": 2,
     "last_purchase_date": date(2025, 8, 1)},
    {"name": "Active", "total_spent": 900.0, "purchase_count": 20,
     "last_purchase_date": date(2026, 7, 30)},
]


class _FakeDB:
    """_segments never touches the session itself — segment_summary does."""


def _patch_summary(monkeypatch, payload):
    async def fake(_store_id, _db):
        return payload
    monkeypatch.setattr("app.services.customer_service.segment_summary", fake)


# ── The seam that caused the 500 ─────────────────────────────────────────────

def test_segments_accepts_the_real_shape_rfm_actually_returns(monkeypatch):
    """
    The regression test for the outage. rfm.summarize returns a LIST; reading
    it with .items() raised AttributeError and 500'd the whole dashboard.
    """
    real = rfm.summarize(CUSTOMERS, today=date(2026, 8, 4))
    assert isinstance(real, list), "producer shape changed — update the adapter"

    _patch_summary(monkeypatch, {"segments": real})
    out = _run(ENG._segments("store", _FakeDB()))

    assert isinstance(out, dict)
    assert out, "real customer data must produce at least one segment"
    for name, stats in out.items():
        assert isinstance(name, str) and name
        assert stats["count"] > 0
        assert stats["avg_spend"] >= 0


def test_segments_derives_average_spend_because_rfm_reports_totals(monkeypatch):
    """
    rfm reports total_spent. The win-back detector multiplies by a PER-CUSTOMER
    response rate, so passing a total straight through would overstate the
    opportunity by the size of the segment — here, 4x — on a dollar figure the
    owner is asked to act on.
    """
    _patch_summary(monkeypatch,
                   {"segments": [{"segment": "At Risk", "count": 4, "total_spent": 400.0}]})
    out = _run(ENG._segments("store", _FakeDB()))
    assert out["At Risk"]["avg_spend"] == 100.0
    assert out["At Risk"]["total_spent"] == 400.0


def test_segments_still_accepts_a_mapping(monkeypatch):
    """Forward-compatible: if summarize() ever returns a mapping, don't break."""
    _patch_summary(monkeypatch,
                   {"segments": {"Inactive": {"count": 2, "avg_spend": 50.0}}})
    out = _run(ENG._segments("store", _FakeDB()))
    assert out["Inactive"] == {"count": 2, "avg_spend": 50.0, "total_spent": 0.0}


def test_the_winback_detector_can_consume_what_segments_produces(monkeypatch):
    """
    End-to-end across the seam: producer → adapter → consumer. This is the test
    that would have caught the outage, because it never hand-writes the shape.
    """
    from app.services.bi import opportunities as OPP

    _patch_summary(monkeypatch, {"segments": rfm.summarize(CUSTOMERS, date(2026, 8, 4))})
    segments = _run(ENG._segments("store", _FakeDB()))
    OPP.detect_winback(segments)  # must not raise, whatever the data


# ── Optional features must degrade, not explode ──────────────────────────────

@pytest.mark.parametrize("junk", [
    None,
    {},
    {"segments": None},
    {"segments": []},
    {"segments": "not a collection"},
    {"segments": [None, 42, "text"]},
    {"segments": [{"no_name_key": 1}]},
    {"segments": [{"segment": "At Risk", "count": 0, "total_spent": 0}]},
])
def test_segments_never_raises_on_malformed_input(monkeypatch, junk):
    """
    Plenty of stores never upload a customer file. A missing optional feature
    must cost the owner one opportunity card, not the entire Business Control
    Center.
    """
    _patch_summary(monkeypatch, junk)
    out = _run(ENG._segments("store", _FakeDB()))
    assert isinstance(out, dict)
    assert all(v["count"] > 0 for v in out.values())


def test_segments_returns_empty_when_the_service_raises(monkeypatch):
    async def boom(_store_id, _db):
        raise RuntimeError("customers table missing")
    monkeypatch.setattr("app.services.customer_service.segment_summary", boom)
    assert _run(ENG._segments("store", _FakeDB())) == {}


# ── The snapshot must describe ONE report ────────────────────────────────────

class _CapturingDB:
    """Captures the statement instead of running it, so the WHERE clause itself
    can be asserted without a live Postgres."""

    def __init__(self):
        self.statements = []

    async def execute(self, stmt):
        self.statements.append(stmt)

        class _Result:
            def all(self_inner):
                return []

            def scalars(self_inner):
                class _S:
                    def first(self_s):
                        return None

                    def all(self_s):
                        return []
                return _S()
        return _Result()


def _sql(stmt):
    """Compile against Postgres — DISTINCT ON is a Postgres-only construct and
    the default dialect warns that it silently ignores it."""
    from sqlalchemy.dialects import postgresql
    return str(stmt.compile(dialect=postgresql.dialect()))


def test_the_snapshot_is_scoped_to_a_single_upload():
    """
    The regression test for an 85x overstatement.

    Without this filter the snapshot merged every report the store had ever
    uploaded: products that appeared in an old report but not the current one
    survived with stock 0 and historical sales, which the engine read as
    "sold out, losing sales". On real data that inflated the reorder
    opportunity from $9,995 to $846,785 — against a store whose entire monthly
    revenue is $66,753.
    """
    db = _CapturingDB()
    upload = "11111111-2222-3333-4444-555555555555"
    _run(ENG._latest_snapshot("store", db, upload))

    sql = _sql(db.statements[0])
    assert "upload_id" in sql, "snapshot is not scoped to one upload"
    assert "DISTINCT ON" in sql.upper(), "page reprints would be double-counted"


def test_the_snapshot_falls_back_to_all_rows_when_no_upload_is_known():
    """A store mid-first-upload must still render, not error."""
    db = _CapturingDB()
    _run(ENG._latest_snapshot("store", db, None))
    assert "upload_id" not in _sql(db.statements[0])


def test_the_latest_upload_query_requires_sales_rows():
    """
    Joined to normalized_sales on purpose: a customer file or a failed parse
    leaves an upload row with no sales behind it, and scoping the dashboard to
    an empty upload would blank the entire Business Control Center.
    """
    db = _CapturingDB()
    _run(ENG._latest_upload_id("store", db))
    sql = _sql(db.statements[0]).lower()
    assert "join" in sql and "normalized_sales" in sql and "uploaded_reports" in sql


# ── The silent seam: a wrong .get() key fails quietly ────────────────────────

def test_campaign_performance_exposes_the_key_the_engine_reads():
    """
    _campaigns reads total_revenue_lift. Asserting the producer's key here
    means renaming it breaks a test instead of silently disabling the
    campaign-repeat detector — which is exactly how that bug survived.
    """
    import inspect

    from app.services import campaign_service
    source = inspect.getsource(campaign_service.get_campaign_performance)
    assert '"total_revenue_lift"' in source, (
        "campaign_service no longer returns total_revenue_lift — "
        "engine._campaigns must be updated to match"
    )
