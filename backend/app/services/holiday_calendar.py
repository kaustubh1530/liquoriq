"""
services/holiday_calendar.py — US drinking-holiday calendar (Phase 15)

Liquor sales are driven by the calendar. This module knows which US holidays
and events move alcohol, when they land, and what to push for each — so the AI
strategy engine can build timely, themed campaigns instead of generic ones.

Pure + testable: no DB, no network. get_upcoming_holidays(today, days) returns
the events inside the window, soonest first.

Floating holidays (Super Bowl, Mardi Gras, Diwali) are hard to compute, so
they're hardcoded for 2025-2027 and can be extended. Fixed and nth-weekday
holidays compute for any year.
"""

from datetime import date, timedelta


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """n-th weekday of a month (weekday: Mon=0 … Sun=6). n=1 → first."""
    d = date(year, month, 1)
    offset = (weekday - d.weekday()) % 7
    return d + timedelta(days=offset + (n - 1) * 7)


def _last_weekday(year: int, month: int, weekday: int) -> date:
    """Last given weekday of a month."""
    if month == 12:
        nxt = date(year + 1, 1, 1)
    else:
        nxt = date(year, month + 1, 1)
    d = nxt - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - weekday) % 7)


# Floating holidays that don't follow a simple rule → hardcoded (extend yearly)
_FLOATING = {
    "super_bowl":  {2025: date(2025, 2, 9),  2026: date(2026, 2, 8),  2027: date(2027, 2, 14)},
    "mardi_gras":  {2025: date(2025, 3, 4),  2026: date(2026, 2, 17), 2027: date(2027, 2, 9)},
    "diwali":      {2025: date(2025, 10, 20), 2026: date(2026, 11, 8), 2027: date(2027, 10, 29)},
}


def _events_for_year(year: int) -> list[dict]:
    """All tracked events for one calendar year, each with date + campaign guidance."""
    thanksgiving = _nth_weekday(year, 11, 3, 4)   # 4th Thursday of November
    return [
        {"key": "new_years_eve", "name": "New Year's Eve", "date": date(year, 1, 1) if False else date(year, 12, 31),
         "why": "Biggest single night for Champagne, sparkling wine, and premium spirits.",
         "push": "Champagne, Prosecco, Cava, premium whiskey/vodka, party bundles"},
        {"key": "valentines", "name": "Valentine's Day", "date": date(year, 2, 14),
         "why": "Couples buy wine, Champagne, and gift-worthy bottles.",
         "push": "Rosé, Champagne, red blends, chocolate-pairing wines, gift sets"},
        {"key": "super_bowl", "name": "Super Bowl", "date": _FLOATING["super_bowl"].get(year),
         "why": "Huge beer + party-spirits day; snacks and cases move fast.",
         "push": "Beer cases, hard seltzer, tequila, party-size spirits, mixers"},
        {"key": "mardi_gras", "name": "Mardi Gras", "date": _FLOATING["mardi_gras"].get(year),
         "why": "Festive cocktails and party drinking.",
         "push": "Hurricane mixers, rum, whiskey, colorful cocktail kits"},
        {"key": "st_patricks", "name": "St. Patrick's Day", "date": date(year, 3, 17),
         "why": "Irish whiskey, stout, and green-themed drinks spike.",
         "push": "Irish whiskey, Guinness/stouts, Irish cream, green cocktails"},
        {"key": "kentucky_derby", "name": "Kentucky Derby", "date": _nth_weekday(year, 5, 5, 1),
         "why": "Bourbon and mint julep season.",
         "push": "Bourbon, mint julep kits, Southern-style spirits"},
        {"key": "cinco_de_mayo", "name": "Cinco de Mayo", "date": date(year, 5, 5),
         "why": "Tequila, margaritas, and Mexican beer explode.",
         "push": "Tequila, mezcal, margarita mixers, Mexican beer, limes"},
        {"key": "memorial_day", "name": "Memorial Day Weekend", "date": _last_weekday(year, 5, 0),
         "why": "Start of summer BBQ season — beer, seltzer, rosé.",
         "push": "Beer cases, hard seltzer, rosé, frozen-cocktail pouches"},
        {"key": "fathers_day", "name": "Father's Day", "date": _nth_weekday(year, 6, 6, 3),
         "why": "Premium whiskey and craft beer as gifts.",
         "push": "Premium bourbon/scotch, craft beer, gift sets"},
        {"key": "independence_day", "name": "July 4th", "date": date(year, 7, 4),
         "why": "One of the biggest beer + seltzer weekends of the year.",
         "push": "Beer cases, hard seltzer, vodka, rosé, red-white-blue bundles"},
        {"key": "labor_day", "name": "Labor Day Weekend", "date": _nth_weekday(year, 9, 1, 1),
         "why": "Last big summer BBQ push.",
         "push": "Beer, seltzer, rosé, tequila, summer-cocktail kits"},
        {"key": "oktoberfest", "name": "Oktoberfest", "date": date(year, 9, 20),
         "why": "Craft and German beer season.",
         "push": "Märzen/Oktoberfest beers, craft lagers, steins"},
        {"key": "halloween", "name": "Halloween", "date": date(year, 10, 31),
         "why": "Party spirits, wine, and themed cocktails.",
         "push": "Vodka, rum, wine, orange/black themed cocktail kits"},
        {"key": "diwali", "name": "Diwali", "date": _FLOATING["diwali"].get(year),
         "why": "Big gifting and celebration in the DMV's South Asian community.",
         "push": "Premium whiskey, wine gift sets, sparkling wine"},
        {"key": "blackout_wednesday", "name": "Thanksgiving Eve (Blackout Wednesday)",
         "date": thanksgiving - timedelta(days=1),
         "why": "Historically one of the BUSIEST bar/liquor nights of the year.",
         "push": "Beer, whiskey, vodka, party spirits — stock heavy"},
        {"key": "thanksgiving", "name": "Thanksgiving", "date": thanksgiving,
         "why": "Wine for the table + hosting spirits.",
         "push": "Pinot Noir, Chardonnay, Beaujolais, cider, hosting spirits"},
        {"key": "christmas", "name": "Christmas", "date": date(year, 12, 25),
         "why": "Peak gifting season — premium bottles and gift sets.",
         "push": "Premium spirits, Champagne, wine gift sets, eggnog/cream liqueurs"},
    ]


def get_upcoming_holidays(today: date | None = None, days: int = 45) -> list[dict]:
    """
    Events landing within `days` of `today`, soonest first. Each item adds
    `days_away`. Looks across this year and next so a December window still
    catches January events.
    """
    today = today or date.today()
    horizon = today + timedelta(days=days)

    events = _events_for_year(today.year) + _events_for_year(today.year + 1)
    upcoming = []
    for e in events:
        d = e.get("date")
        if d is None:
            continue
        if today <= d <= horizon:
            upcoming.append({**e, "days_away": (d - today).days})

    # de-dupe by key (a holiday can appear from both years), keep soonest
    seen = {}
    for e in sorted(upcoming, key=lambda x: x["date"]):
        seen.setdefault(e["key"], e)
    return sorted(seen.values(), key=lambda x: x["days_away"])
