"""
services/rfm.py — RFM scoring, segmentation, and marketing recommendations (Phase 19)

Pure functions (no DB) so they're easy to test and reason about.

RFM:
  Recency   — days since last purchase (fewer = better)
  Frequency — number of purchases/visits
  Monetary  — total lifetime spend

Each is scored 1-5 with fixed, tunable thresholds (fixed beats quintiles for a
small/new store — stable and explainable). Segments are derived from the three
scores with a clear priority order. Every segment has a deterministic marketing
recommendation.
"""

from datetime import date

# ── Score thresholds (tunable) ────────────────────────────────────────────────
# Recency: days since last purchase → score (5 = most recent)
_RECENCY_DAYS = [(30, 5), (60, 4), (90, 3), (180, 2)]   # else 1
# Frequency: purchase count → score
_FREQUENCY = [(12, 5), (6, 4), (3, 3), (2, 2)]          # else 1
# Monetary: lifetime spend $ → score
_MONETARY = [(1000, 5), (500, 4), (250, 3), (100, 2)]   # else 1

SEGMENTS = ["VIP", "High Value", "Loyal", "New", "At Risk", "Inactive", "Regular"]

SEGMENT_RECOMMENDATIONS = {
    "VIP":        "Reward them: early access to allocated bottles, an exclusive perk, a personal thank-you.",
    "High Value": "Upsell premium & bundles; invite to tastings; recommend pairings.",
    "Loyal":      "Loyalty rewards and referral asks; restock reminders on their favorites.",
    "New":        "Welcome offer + a nudge toward a second purchase to build the habit.",
    "At Risk":    "Win-back: a 'we miss you' message with a time-limited discount.",
    "Inactive":   "Strong reactivation offer, or sunset from active marketing.",
    "Regular":    "Steady promotions; move them up with a bundle or a small loyalty incentive.",
}


def _score(value, table) -> int:
    for threshold, score in table:
        if value >= threshold:
            return score
    return 1


def recency_score(days_since: int | None) -> int:
    if days_since is None:
        return 1
    for max_days, score in _RECENCY_DAYS:
        if days_since <= max_days:
            return score
    return 1


def frequency_score(count: int) -> int:
    return _score(count or 0, _FREQUENCY)


def monetary_score(total_spent: float) -> int:
    return _score(total_spent or 0, _MONETARY)


def segment(r: int, f: int, m: int) -> str:
    """
    Priority order matters — retention signals first so valuable-but-slipping
    customers surface as 'At Risk' rather than being hidden under 'High Value'.
    """
    if r >= 4 and f >= 4 and m >= 4:
        return "VIP"
    if r <= 2 and (f >= 3 or m >= 3):
        return "At Risk"
    if r == 1:
        return "Inactive"
    if m >= 4:
        return "High Value"
    if f >= 4:
        return "Loyal"
    if r >= 4 and f <= 2:
        return "New"
    return "Regular"


def compute_rfm(customer: dict, today: date | None = None) -> dict:
    """
    customer: {last_purchase_date: date|None, purchase_count: int, total_spent: float}
    Returns scores, recency_days, segment, and a recommendation.
    """
    today = today or date.today()
    last = customer.get("last_purchase_date")
    recency_days = (today - last).days if last else None
    count = int(customer.get("purchase_count") or 0)
    spent = float(customer.get("total_spent") or 0)

    r = recency_score(recency_days)
    f = frequency_score(count)
    m = monetary_score(spent)
    seg = segment(r, f, m)

    return {
        "recency_days": recency_days,
        "r_score": r, "f_score": f, "m_score": m,
        "segment": seg,
        "recommendation": SEGMENT_RECOMMENDATIONS[seg],
    }


def summarize(customers: list[dict], today: date | None = None) -> list[dict]:
    """Per-segment rollup: count, total spend, recommendation. Empty → all-zero segments."""
    today = today or date.today()
    buckets = {s: {"segment": s, "count": 0, "total_spent": 0.0} for s in SEGMENTS}
    for c in customers:
        seg = compute_rfm(c, today)["segment"]
        buckets[seg]["count"] += 1
        buckets[seg]["total_spent"] += float(c.get("total_spent") or 0)
    out = []
    for s in SEGMENTS:
        b = buckets[s]
        b["total_spent"] = round(b["total_spent"], 2)
        b["recommendation"] = SEGMENT_RECOMMENDATIONS[s]
        out.append(b)
    return out
