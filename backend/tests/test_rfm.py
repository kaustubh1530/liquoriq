"""tests/test_rfm.py — RFM scoring, segmentation, recommendations (Phase 19)"""

from datetime import date

from app.services import rfm


def test_recency_score_thresholds():
    assert rfm.recency_score(10) == 5
    assert rfm.recency_score(45) == 4
    assert rfm.recency_score(75) == 3
    assert rfm.recency_score(120) == 2
    assert rfm.recency_score(400) == 1
    assert rfm.recency_score(None) == 1


def test_frequency_and_monetary_scores():
    assert rfm.frequency_score(15) == 5
    assert rfm.frequency_score(1) == 1
    assert rfm.monetary_score(1200) == 5
    assert rfm.monetary_score(50) == 1


def test_segment_vip():
    assert rfm.segment(5, 5, 5) == "VIP"


def test_segment_at_risk_before_high_value():
    # Big spender who hasn't come recently → win-back, not "High Value"
    assert rfm.segment(1, 3, 5) == "At Risk"


def test_segment_inactive():
    assert rfm.segment(1, 1, 1) == "Inactive"


def test_segment_high_value_and_loyal_and_new():
    assert rfm.segment(4, 2, 5) == "High Value"
    assert rfm.segment(3, 5, 2) == "Loyal"
    assert rfm.segment(5, 1, 1) == "New"
    assert rfm.segment(3, 3, 3) == "Regular"


def test_every_segment_has_a_recommendation():
    for seg in rfm.SEGMENTS:
        assert rfm.SEGMENT_RECOMMENDATIONS.get(seg)


def test_compute_rfm_full():
    today = date(2026, 7, 25)
    cust = {"last_purchase_date": date(2026, 7, 20), "purchase_count": 14, "total_spent": 2000}
    out = rfm.compute_rfm(cust, today)
    assert out["recency_days"] == 5
    assert (out["r_score"], out["f_score"], out["m_score"]) == (5, 5, 5)
    assert out["segment"] == "VIP"
    assert out["recommendation"]


def test_summarize_empty_returns_all_zero_segments():
    summary = rfm.summarize([], date(2026, 7, 25))
    assert len(summary) == len(rfm.SEGMENTS)
    assert all(b["count"] == 0 and b["total_spent"] == 0.0 for b in summary)


def test_summarize_counts_and_totals():
    today = date(2026, 7, 25)
    customers = [
        {"last_purchase_date": date(2026, 7, 20), "purchase_count": 14, "total_spent": 2000},  # VIP
        {"last_purchase_date": date(2026, 1, 1), "purchase_count": 1, "total_spent": 20},        # Inactive
    ]
    summary = {b["segment"]: b for b in rfm.summarize(customers, today)}
    assert summary["VIP"]["count"] == 1
    assert summary["VIP"]["total_spent"] == 2000.0
    assert summary["Inactive"]["count"] == 1
