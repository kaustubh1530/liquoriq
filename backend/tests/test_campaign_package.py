"""
tests/test_campaign_package.py — PHASE 23.8: the campaign, in one folder.

Two things are under test, and they are the two things that would hurt an owner
who trusted the ZIP:

1. THE PACKAGE IS A RENDERING OF THE WORKSPACE STATE, NOT A SECOND OPINION.
   The copy in the folder is the copy on the screen, edits and all. A ZIP that
   contained the AI's original SMS after the owner had rewritten it would be
   discovered at the printer, or worse, by his customers.

2. A MISSING PIECE IS NAMED, NEVER FATAL. Half a campaign still packages. The
   README says what is not in there yet and where to make it.
"""

import zipfile
from io import BytesIO

import pytest
from PIL import Image

from app.services import campaign_package as PKG
from app.services import campaign_workspace as WS


def state(**over) -> dict:
    base = {
        "status": "draft",
        "context": {"summary": {
            "campaign": "Labor Day Weekend Whiskey Push",
            "occasion": "Labor Day Weekend",
            "goal": "Move slow whiskey stock before the holiday",
            "audience": "Weekend regulars",
            "offer": "Buy 2, save $10 — Buffalo Trace at $27.99",
            "products": ["Buffalo Trace 750ML", "Bulleit 1.75L"],
            "expected_outcome": "Higher basket size",
        }},
        "copy": {"social": "Raise a glass this Labor Day.",
                 "email_subject": "Your long weekend, sorted",
                 "email": "Hi there,\n\nStock up before Monday.",
                 "sms": "Buffalo Trace $27.99 this weekend only.",
                 "vivino": "", "edited": []},
        "schedule": {"scheduled_for": None, "preset": None},
    }
    base.update(over)
    return base


def no_assets() -> dict:
    return {"ad_png": None, "labels": [], "sheet_pdf": None, "platform": None,
            "notes": []}


def png(w=600, h=600) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (w, h), (200, 120, 60)).save(buf, format="PNG")
    return buf.getvalue()


def entries(blob: bytes) -> list[str]:
    with zipfile.ZipFile(BytesIO(blob)) as z:
        return z.namelist()


def read(blob: bytes, name: str) -> bytes:
    with zipfile.ZipFile(BytesIO(blob)) as z:
        return z.read(name)


# ── One source of truth for the words ────────────────────────────────────────

def test_the_zip_carries_the_owners_edit_not_the_ai_original():
    """The whole reason resolve_copy exists in one place. He edits the SMS,
    sees the edit on screen, and must find that same edit in the folder he
    sends to print."""
    import types
    strategy = types.SimpleNamespace(
        social_caption="AI social", email_subject="AI subject",
        email_body="AI email", sms_copy="AI sms", vivino_listing="")
    resolved = WS.resolve_copy(strategy, {"sms": "Come in Friday, $27.99"})

    _, blob = PKG.build(state(copy=resolved), "Shop", no_assets())
    sms = read(blob, [n for n in entries(blob) if n.endswith("sms.txt")][0]).decode()
    assert "Come in Friday" in sms
    assert "AI sms" not in sms


def test_the_package_never_reaches_past_the_state_for_copy():
    """build() takes a dict, not a strategy row. It cannot re-merge an override
    differently from the page, because it has nothing to re-merge from."""
    import inspect
    source = inspect.getsource(PKG.build)
    for reaching in ("social_caption", "sms_copy", "email_body", "db"):
        assert reaching not in source


def test_the_email_subject_travels_with_the_email():
    _, blob = PKG.build(state(), "Shop", no_assets())
    email = read(blob, [n for n in entries(blob) if n.endswith("email.txt")][0]).decode()
    assert email.startswith("Subject: Your long weekend, sorted")
    assert "Stock up before Monday" in email


def test_an_empty_channel_is_left_out_rather_than_shipped_blank():
    """An empty sms.txt reads as a broken generator, not as a campaign with
    no SMS."""
    files = PKG.copy_files({"social": "hello", "sms": "   ", "email": ""})
    assert [p for p, _ in files] == ["copy/social.txt"]


def test_the_sms_file_says_what_it_will_cost_to_send():
    files = dict(PKG.copy_files({"sms": "x" * 200}))
    assert "2 SMS segment(s)" in files["copy/sms.txt"]


# ── Missing pieces are named, never fatal ────────────────────────────────────

def test_a_campaign_with_nothing_made_yet_still_packages():
    name, blob = PKG.build(state(), "Shop", no_assets())
    assert name.endswith(".zip")
    assert any(n.endswith("README.txt") for n in entries(blob))


def test_the_readme_names_what_is_missing_and_where_to_make_it():
    _, blob = PKG.build(state(), "Shop", no_assets())
    text = read(blob, [n for n in entries(blob) if n.endswith("README.txt")][0]).decode()
    assert "NOT IN HERE YET" in text
    assert "Ad Creator" in text or "campaign workspace" in text
    assert "Label Studio" in text


def test_a_failed_asset_is_reported_rather_than_swallowed():
    assets = no_assets()
    assets["notes"].append('The label "Buffalo Trace" could not be rendered.')
    _, blob = PKG.build(state(), "Shop", assets)
    text = read(blob, [n for n in entries(blob) if n.endswith("README.txt")][0]).decode()
    assert "could not be rendered" in text


def test_the_readme_repeats_that_scheduling_is_not_sending():
    """It is repeated in the ZIP because the ZIP is what leaves the building.
    An owner who believes an SMS will send itself has been failed badly."""
    _, blob = PKG.build(state(schedule={"scheduled_for": "2026-09-04T17:00:00"}),
                        "Shop", no_assets())
    text = read(blob, [n for n in entries(blob) if n.endswith("README.txt")][0]).decode()
    assert "not automated" in text


# ── What is actually in the folder ───────────────────────────────────────────

def test_everything_lands_under_one_named_folder():
    """Unzipping must not spray twelve files across the Downloads folder."""
    _, blob = PKG.build(state(), "Shop", no_assets())
    tops = {n.split("/")[0] for n in entries(blob)}
    assert tops == {"labor-day-weekend-whiskey-push"}


def test_the_ad_and_the_labels_are_included_when_they_exist():
    assets = no_assets()
    assets["ad_png"] = png()
    assets["labels"] = [("Buffalo Trace $27.99", png(300, 400)),
                        ("Bulleit $39.99", png(300, 400))]
    assets["sheet_pdf"] = b"%PDF-1.4 fake"
    _, blob = PKG.build(state(), "Shop", assets)
    names = entries(blob)
    assert any(n.endswith("ad/advertisement.png") for n in names)
    assert sum(1 for n in names if "/labels/" in n and n.endswith(".png")) == 2
    assert any(n.endswith("print-sheet.pdf") for n in names)


def test_labels_are_numbered_so_they_keep_their_order():
    assets = no_assets()
    assets["labels"] = [("B", png(80, 80)), ("A", png(80, 80))]
    _, blob = PKG.build(state(), "Shop", assets)
    label_files = sorted(n for n in entries(blob) if "/labels/" in n)
    assert "01-b.png" in label_files[0] and "02-a.png" in label_files[1]


def test_platform_copy_rides_along_with_the_ad():
    assets = no_assets()
    assets["platform"] = {"instagram_caption": "IG!", "facebook_post": "",
                          "ubereats_description": "Ubes"}
    _, blob = PKG.build(state(), "Shop", assets)
    names = entries(blob)
    assert any(n.endswith("platform/instagram.txt") for n in names)
    assert any(n.endswith("platform/ubereats.txt") for n in names)
    assert not any(n.endswith("platform/facebook.txt") for n in names)


# ── The names have to survive a real computer ────────────────────────────────

@pytest.mark.parametrize("title,expected", [
    ("50% Off — Tito's/Bulleit", "50-off-tito-s-bulleit"),
    ("   ", "campaign"),
    ("Café Noël 🎄", "caf-no-l"),
])
def test_titles_become_names_every_operating_system_accepts(title, expected):
    """A ZIP that will not unpack on Windows because an entry is called
    "50% Off — Tito's/Bulleit" is a broken deliverable."""
    assert PKG.slug(title) == expected


def test_a_slug_can_never_be_endless():
    assert len(PKG.slug("word " * 100)) <= 60


# ── The summary PDF ──────────────────────────────────────────────────────────

def test_the_summary_is_a_real_pdf():
    assert PKG.summary_pdf(state(), "Shop")[:5] == b"%PDF-"


def test_the_summary_holds_a_long_campaign_without_losing_the_end():
    """Text has to flow onto a second page rather than run off the first."""
    doc = PKG._Doc()
    doc.text("paragraph. " * 900)
    assert len(doc.pages) > 1

    long_copy = dict(state()["copy"], email="paragraph. " * 900)
    assert PKG.summary_pdf(state(copy=long_copy), "Shop")[:5] == b"%PDF-"


def test_the_summary_survives_an_unreadable_image():
    """A corrupt ad must not deny the owner the brief."""
    assert PKG.summary_pdf(state(), "Shop", ad_png=b"not an image")[:5] == b"%PDF-"


def test_the_summary_survives_an_empty_campaign():
    assert PKG.summary_pdf({"context": {}, "copy": {}, "schedule": {}},
                           "Shop")[:5] == b"%PDF-"


def test_the_summary_is_in_the_zip_and_is_a_pdf():
    _, blob = PKG.build(state(), "Shop", no_assets())
    name = [n for n in entries(blob) if n.endswith("campaign-summary.pdf")][0]
    assert read(blob, name)[:5] == b"%PDF-"
