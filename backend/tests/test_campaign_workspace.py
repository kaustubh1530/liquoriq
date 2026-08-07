"""
tests/test_campaign_workspace.py — PHASE 23.7: the campaign as a project.

The design decision under test is that PROGRESS IS COMPUTED, NEVER STORED.

The obvious alternative — a row of booleans set by whichever page finished the
work — drifts. A creative gets deleted and the flag stays true. A label is made
outside the workspace and the flag stays false. The owner then sees a progress
bar disagreeing with his own assets, which is worse than no progress bar.
"""

from datetime import date, datetime, timedelta

import pytest

from app.services import campaign_workspace as WS


# ── The schedule presets resolve to real times ───────────────────────────────

def test_every_preset_resolves_to_a_real_datetime():
    """
    Resolved server-side so a schedule means the same thing on any device, and
    so a worker reading these rows later never has to interpret "Friday
    evening".
    """
    for option in WS.schedule_options():
        if option["preset"] == "custom":
            assert option["when"] is None
            continue
        assert datetime.fromisoformat(option["when"])


def test_friday_evening_lands_on_a_friday():
    monday = date(2026, 8, 3)
    when = WS.resolve_schedule("friday_evening", None, today=monday)
    assert when.weekday() == 4
    assert when.hour == 17


def test_saturday_morning_lands_on_a_saturday():
    when = WS.resolve_schedule("saturday_morning", None, today=date(2026, 8, 3))
    assert when.weekday() == 5


def test_a_preset_on_its_own_day_rolls_to_next_week():
    """Scheduling "Friday evening" on a Friday means NEXT Friday, not an hour
    from now — the owner is planning, not panicking."""
    friday = date(2026, 8, 7)
    when = WS.resolve_schedule("friday_evening", None, today=friday)
    assert when.date() > friday


def test_a_custom_time_always_wins():
    chosen = datetime(2026, 12, 24, 8, 0)
    assert WS.resolve_schedule("friday_evening", chosen) == chosen


def test_an_unknown_preset_resolves_to_nothing_rather_than_guessing():
    assert WS.resolve_schedule("whenever", None) is None


def test_every_option_explains_why_that_window():
    """"Friday evening" without "catches the pre-weekend shop" is a dropdown;
    with it, it is advice."""
    for option in WS.schedule_options():
        assert option["why"], option["preset"]


# ── The pipeline ─────────────────────────────────────────────────────────────

def test_the_pipeline_covers_the_whole_campaign():
    keys = [s["key"] for s in WS.STEPS]
    assert keys == ["strategy", "ad", "labels", "social", "email", "sms",
                    "scheduled", "roi"]


def test_copy_counts_as_done_when_the_strategy_wrote_it():
    import types
    s = types.SimpleNamespace(social_caption="Raise a glass", email_body="",
                              sms_copy="")
    assert WS._copy_present(s, "social", None) is True
    assert WS._copy_present(s, "email", None) is False


def test_an_owner_edit_counts_even_when_the_strategy_was_empty():
    import types
    s = types.SimpleNamespace(social_caption="", email_body="", sms_copy="")
    assert WS._copy_present(s, "sms", {"sms": "Come in Friday"}) is True


def test_whitespace_is_not_copy():
    import types
    s = types.SimpleNamespace(social_caption="   ", email_body="", sms_copy="")
    assert WS._copy_present(s, "social", None) is False


# ── The labels step (PHASE 23.8) ─────────────────────────────────────────────
#
# Before the migration, labels had no strategy_id, so the step could only ask
# "does this shop have ANY saved label?" — a tag made for July's clearance
# ticked off June's Father's Day campaign. It now asks about this campaign.

def test_labels_made_for_this_campaign_complete_the_step():
    step = WS._labels_step(linked=2, unlinked=0)
    assert step["done"] is True
    assert "2 labels" in step["detail"]


def test_one_label_is_not_called_two():
    assert "1 label for" in WS._labels_step(linked=1, unlinked=5)["detail"]


def test_someone_elses_labels_never_complete_this_campaign():
    """The whole point of the migration. A label made for another campaign —
    or before there were campaigns — is not this campaign's work."""
    step = WS._labels_step(linked=0, unlinked=6)
    assert step["done"] is False
    assert "none for this campaign" in step["detail"]


def test_unlinked_labels_are_still_mentioned():
    """"You have 6, none on this campaign" tells the owner where to look;
    silence would read as "you have no labels", which is false."""
    assert "6" in WS._labels_step(linked=0, unlinked=6)["detail"]


def test_no_labels_at_all_says_nothing_rather_than_zero():
    assert WS._labels_step(linked=0, unlinked=0) == {"done": False, "detail": ""}


def test_the_labels_step_no_longer_claims_to_be_weak():
    """`weak: true` was Phase 23.7 being honest about a signal it could not
    fix. The migration fixed it, so the apology has to go too — a flag saying
    "don't trust this" outliving the reason is its own kind of lie."""
    for linked, unlinked in [(0, 0), (0, 4), (3, 0), (3, 4)]:
        assert "weak" not in WS._labels_step(linked, unlinked)


def test_the_labels_step_is_scoped_to_the_strategy():
    import inspect
    source = inspect.getsource(WS._has_labels)
    assert "strategy_id" in source
    source = inspect.getsource(WS.build_state)
    assert "_has_labels(strategy.id" in source


# ── The coach line ───────────────────────────────────────────────────────────

def test_the_coach_line_names_what_is_left_to_do():
    line = WS._coach_line(
        {"summary": {"expected_outcome": "Higher basket size",
                     "occasion": "Labor Day Weekend"}},
        [{"key": "ad", "label": "Advertisement", "done": False},
         {"key": "sms", "label": "SMS", "done": False},
         {"key": "strategy", "label": "Strategy", "done": True}],
    )
    assert "Labor Day" in line
    assert "advertisement" in line.lower()


def test_the_coach_line_survives_an_empty_strategy():
    assert isinstance(WS._coach_line({}, []), str)


def test_the_coach_line_is_not_a_model_call():
    """
    It sits above everything else on the page. A GPT call here would put a
    spinner in the first thing the owner reads, on every visit, for prose that
    changes only when the strategy does.
    """
    import inspect
    source = inspect.getsource(WS._coach_line)
    for forbidden in ("openai", "generate_json", "await ", "async"):
        assert forbidden not in source


# ── Progress is computed, not stored ─────────────────────────────────────────

def test_the_model_stores_no_progress_flags():
    """
    The whole point. If a done-flag existed, something would have to keep it in
    sync with the real assets, and it would eventually fail to.
    """
    import inspect

    from app.models import campaign_workspace as MODEL
    source = inspect.getsource(MODEL)
    for flag in ("ad_done", "labels_done", "sms_done", "email_done",
                 "social_done", "progress"):
        assert flag not in source


def test_the_model_stores_no_asset_content():
    """Copying the ad or the labels here would create a second source of truth
    for the same thing, and the two would drift."""
    import inspect

    from app.models import campaign_workspace as MODEL
    source = inspect.getsource(MODEL)
    for content in ("image_url", "instagram_caption", "label_json", "design_json"):
        assert content not in source


def test_state_is_built_by_reading_real_assets():
    import inspect
    source = inspect.getsource(WS.build_state)
    assert "_has_creative" in source and "_has_labels" in source
