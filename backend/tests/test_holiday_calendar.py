"""tests/test_holiday_calendar.py — US drinking-holiday calendar (Phase 15)"""

from datetime import date

from app.services.holiday_calendar import (
    _last_weekday, _nth_weekday, get_upcoming_holidays,
)


def test_nth_weekday_thanksgiving_2026():
    # Thanksgiving 2026 = 4th Thursday of November = Nov 26
    assert _nth_weekday(2026, 11, 3, 4) == date(2026, 11, 26)


def test_last_weekday_memorial_day_2026():
    # Memorial Day 2026 = last Monday of May = May 25
    assert _last_weekday(2026, 5, 0) == date(2026, 5, 25)


def test_upcoming_window_picks_soon_events_first():
    # From Dec 20 2026, NYE (Dec 31) should be in a 45-day window and near the top
    events = get_upcoming_holidays(date(2026, 12, 20), days=45)
    keys = [e["key"] for e in events]
    assert "new_years_eve" in keys
    assert events == sorted(events, key=lambda e: e["days_away"])


def test_window_crosses_year_boundary():
    # Late December should still catch January/February events within the window
    events = get_upcoming_holidays(date(2026, 12, 28), days=50)
    keys = [e["key"] for e in events]
    assert "new_years_eve" in keys


def test_events_have_campaign_guidance():
    events = get_upcoming_holidays(date(2026, 6, 1), days=45)
    assert events, "expected some summer events"
    for e in events:
        assert e["why"] and e["push"] and e["days_away"] >= 0


def test_blackout_wednesday_before_thanksgiving():
    events = get_upcoming_holidays(date(2026, 11, 20), days=14)
    by_key = {e["key"]: e for e in events}
    assert by_key["blackout_wednesday"]["date"] == date(2026, 11, 25)
    assert by_key["thanksgiving"]["date"] == date(2026, 11, 26)
