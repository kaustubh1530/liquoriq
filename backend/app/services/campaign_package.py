"""
services/campaign_package.py — PHASE 23.8: the whole campaign, in one folder.

THE PROBLEM

Everything the owner needs to actually run the campaign exists — the ad, the
shelf labels, the social caption, the SMS — and every piece lives behind a
different button. Running a promotion means visiting four screens, downloading
four things, and remembering which price went with which bottle. The work was
finished; collecting it was still his job.

WHAT THIS IS

One ZIP: the finished ad, the labels rendered at print resolution, a printable
label sheet, every piece of copy as a plain text file, and a summary PDF he can
hand to whoever is minding the shop on Saturday.

TWO RULES THIS MODULE FOLLOWS

1. THE PACKAGE IS A RENDERING OF THE WORKSPACE STATE, NOT A SECOND OPINION.
   `build()` is handed the exact dict that `campaign_workspace.build_state()`
   put on the screen. It never re-reads the strategy, never re-merges a copy
   override, never re-decides what the offer was. If the ZIP ever disagreed with
   the page, the owner would have no way of knowing which one to believe — and
   the one he sent to the printer is the one that costs money.

2. A MISSING PIECE IS NAMED, NEVER FATAL.
   No ad yet? The ZIP still builds, and the README says so in a sentence that
   tells him where to make one. Refusing to produce anything until the campaign
   is complete would be the system withholding his own work from him.
"""

import logging
import re
import zipfile
from datetime import datetime
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

_FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
_SERIF_BOLD = _FONT_DIR / "DejaVuSerif-Bold.ttf"
_SANS = _FONT_DIR / "DejaVuSans.ttf"
_SANS_BOLD = _FONT_DIR / "DejaVuSans-Bold.ttf"

# A4 at 150 DPI. Print-sane without making a 20 MB PDF out of a page of text.
PAGE = (1240, 1754)
MARGIN = 100
INK = (17, 17, 17)
MUTED = (110, 110, 110)
RULE = (222, 222, 222)
PAPER = (255, 255, 255)

_UNSAFE = re.compile(r"[^a-z0-9]+")


def slug(text: str, fallback: str = "campaign") -> str:
    """
    A file name that survives every operating system the owner might use.

    Campaign titles contain slashes, quotes and emoji. A ZIP that will not
    unpack on Windows because an entry is called "50% Off — Tito's/Bulleit" is
    a broken deliverable, so names are reduced to letters, digits and hyphens.
    """
    cleaned = _UNSAFE.sub("-", (text or "").lower()).strip("-")
    return (cleaned or fallback)[:60]


# ── The text files ───────────────────────────────────────────────────────────

def copy_files(copy: dict) -> list[tuple[str, str]]:
    """
    One .txt per channel, ready to paste.

    Plain text on purpose: the owner is going to select-all and paste this into
    Instagram or his SMS tool, and a .docx would put a font in the way of that.
    Empty channels are left out entirely — an empty sms.txt looks like a bug in
    the generator rather than a campaign that has no SMS.

    The subject line rides at the top of the email file because an email is not
    postable without one, and two files that must be used together are two files
    one of which gets missed.
    """
    files: list[tuple[str, str]] = []
    if (copy.get("social") or "").strip():
        files.append(("copy/social.txt", copy["social"].strip() + "\n"))
    if (copy.get("email") or "").strip():
        subject = (copy.get("email_subject") or "").strip()
        head = f"Subject: {subject}\n\n" if subject else ""
        files.append(("copy/email.txt", head + copy["email"].strip() + "\n"))
    elif (copy.get("email_subject") or "").strip():
        files.append(("copy/email-subject.txt", copy["email_subject"].strip() + "\n"))
    if (copy.get("sms") or "").strip():
        text = copy["sms"].strip()
        segments = (len(text) - 1) // 160 + 1
        files.append(("copy/sms.txt",
                      f"{text}\n\n---\n{len(text)} characters · {segments} SMS segment(s)\n"))
    if (copy.get("vivino") or "").strip():
        files.append(("copy/vivino-listing.txt", copy["vivino"].strip() + "\n"))
    return files


PLATFORM_FILES = [
    ("instagram_caption", "copy/platform/instagram.txt"),
    ("facebook_post", "copy/platform/facebook.txt"),
    ("ubereats_description", "copy/platform/ubereats.txt"),
    ("doordash_description", "copy/platform/doordash.txt"),
    ("website_banner_headline", "copy/platform/website-banner-headline.txt"),
    ("website_banner_text", "copy/platform/website-banner-text.txt"),
]


def platform_copy_files(platform: dict | None) -> list[tuple[str, str]]:
    """The per-platform copy written alongside the ad, when an ad exists."""
    out = []
    for field, path in PLATFORM_FILES:
        text = ((platform or {}).get(field) or "").strip()
        if text:
            out.append((path, text + "\n"))
    return out


def readme(state: dict, store_name: str, included: list[str],
           missing: list[str]) -> str:
    """
    What is in the folder, and what is not.

    The missing list is the part that earns its place. A ZIP that quietly
    contains no labels reads as "the labels failed"; a line saying "No shelf
    labels for this campaign yet — make them in Label Studio" reads as a
    to-do, which is what it is.
    """
    summary = state.get("context", {}).get("summary", {})
    sched = state.get("schedule", {})
    lines = [
        summary.get("campaign") or "Campaign",
        "=" * len(summary.get("campaign") or "Campaign"),
        "",
        f"{store_name} · packaged {datetime.now().strftime('%d %B %Y, %H:%M')}",
        f"Status: {state.get('status', 'draft')}",
    ]
    if sched.get("scheduled_for"):
        lines.append(f"Planned for: {sched['scheduled_for']}")
        lines.append("Sending is not automated — you still launch this yourself.")
    lines += ["", "IN THIS FOLDER", "--------------"]
    lines += [f"  {item}" for item in included]
    if missing:
        lines += ["", "NOT IN HERE YET", "---------------"]
        lines += [f"  {item}" for item in missing]
    lines += [
        "",
        "The prices in the copy and on the labels are the ones you set in",
        "LiquorIQ. Check them against the shelf before printing.",
        "",
    ]
    return "\n".join(lines)


# ── The summary PDF ──────────────────────────────────────────────────────────

class _Doc:
    """A very small flowing-text PDF. Enough for a brief, and no new dependency.

    Pillow already renders every label and print sheet in this codebase, so the
    summary sheet uses it too: one imaging stack to keep working, and a PDF that
    looks like the labels beside it in the same folder.
    """

    def __init__(self) -> None:
        self.pages: list[Image.Image] = []
        self._new_page()

    def _font(self, path: Path, size: int) -> ImageFont.FreeTypeFont:
        try:
            return ImageFont.truetype(str(path), size)
        except OSError:  # pragma: no cover — bundled fonts, but never crash a download
            return ImageFont.load_default()

    def _new_page(self) -> None:
        page = Image.new("RGB", PAGE, PAPER)
        self.pages.append(page)
        self.draw = ImageDraw.Draw(page)
        self.y = MARGIN

    def _room(self, height: int) -> None:
        if self.y + height > PAGE[1] - MARGIN:
            self._new_page()

    def space(self, px: int = 24) -> None:
        self.y += px

    def rule(self) -> None:
        self._room(30)
        self.draw.line([(MARGIN, self.y), (PAGE[0] - MARGIN, self.y)], fill=RULE, width=2)
        self.y += 26

    def text(self, body: str, size: int = 22, bold: bool = False,
             color=INK, leading: float = 1.45) -> None:
        if not body:
            return
        font = self._font(_SANS_BOLD if bold else _SANS, size)
        max_w = PAGE[0] - 2 * MARGIN
        step = int(size * leading)
        for paragraph in str(body).split("\n"):
            if not paragraph.strip():
                self.y += step // 2
                continue
            line = ""
            for word in paragraph.split():
                trial = f"{line} {word}".strip()
                if self.draw.textlength(trial, font=font) <= max_w:
                    line = trial
                    continue
                self._room(step)
                self.draw.text((MARGIN, self.y), line, font=font, fill=color)
                self.y += step
                line = word
            if line:
                self._room(step)
                self.draw.text((MARGIN, self.y), line, font=font, fill=color)
                self.y += step

    def title(self, body: str) -> None:
        self._room(70)
        font = self._font(_SERIF_BOLD, 46)
        for line in _wrap_to(self.draw, body, font, PAGE[0] - 2 * MARGIN):
            self._room(60)
            self.draw.text((MARGIN, self.y), line, font=font, fill=INK)
            self.y += 58

    def eyebrow(self, body: str) -> None:
        self._room(30)
        font = self._font(_SANS_BOLD, 15)
        self.draw.text((MARGIN, self.y), body.upper(), font=font, fill=MUTED)
        self.y += 26

    def field(self, label: str, value: str) -> None:
        if not (value or "").strip():
            return
        self.eyebrow(label)
        self.text(value, size=21)
        self.space(14)

    def picture(self, png: bytes, max_h: int = 520) -> None:
        try:
            img = Image.open(BytesIO(png)).convert("RGB")
        except Exception:  # noqa: BLE001 — a corrupt image must not kill the PDF
            logger.warning("Could not place an image in the summary PDF", exc_info=True)
            return
        max_w = PAGE[0] - 2 * MARGIN
        scale = min(max_w / img.width, max_h / img.height, 1.0)
        img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
        self._room(img.height + 20)
        # Centred: an ad is the one thing on this page anybody looks at.
        self.pages[-1].paste(img, ((PAGE[0] - img.width) // 2, self.y))
        self.y += img.height + 24

    def to_pdf(self) -> bytes:
        buf = BytesIO()
        self.pages[0].save(buf, format="PDF", resolution=150.0, save_all=True,
                           append_images=self.pages[1:])
        return buf.getvalue()


def _wrap_to(draw, text: str, font, max_w: int) -> list[str]:
    lines, line = [], ""
    for word in str(text or "").split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= max_w or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines or [""]


def summary_pdf(state: dict, store_name: str, ad_png: bytes | None = None,
                label_count: int = 0) -> bytes:
    """
    One sheet the owner can print and leave by the till.

    Everything on it comes from `state` — the same dict the workspace page
    renders. Nothing here recomputes a figure or re-merges an override.
    """
    summary = state.get("context", {}).get("summary", {})
    copy = state.get("copy", {})
    sched = state.get("schedule", {})

    doc = _Doc()
    doc.eyebrow(f"{store_name} · campaign brief")
    doc.title(summary.get("campaign") or "Campaign")
    if summary.get("occasion"):
        doc.text(summary["occasion"], size=23, color=MUTED)
    doc.space(10)
    doc.rule()

    doc.field("Business goal", summary.get("goal", ""))
    doc.field("Target audience", summary.get("audience", ""))
    doc.field("Offer", summary.get("offer", ""))
    doc.field("Products", " · ".join(summary.get("products") or []))
    doc.field("Expected impact", summary.get("expected_outcome", ""))

    when = sched.get("scheduled_for")
    if when:
        doc.field("Planned for", str(when).replace("T", " ")[:16])
        doc.text("Sending is not automated — you still launch this yourself.",
                 size=18, color=MUTED)
        doc.space(10)

    if ad_png:
        doc.rule()
        doc.eyebrow("The advertisement")
        doc.picture(ad_png)
    if label_count:
        doc.eyebrow(f"{label_count} shelf label(s) included, plus a printable sheet")
        doc.space(8)

    for label, text in [("Social", copy.get("social")),
                        ("Email subject", copy.get("email_subject")),
                        ("Email", copy.get("email")),
                        ("SMS", copy.get("sms"))]:
        if (text or "").strip():
            doc.rule()
            doc.eyebrow(label)
            doc.text(text.strip(), size=21)

    edited = copy.get("edited") or []
    if edited:
        doc.space(16)
        doc.text(f"Edited by you: {', '.join(edited)}. The AI's original is still "
                 f"saved in LiquorIQ.", size=17, color=MUTED)
    return doc.to_pdf()


# ── The ZIP ──────────────────────────────────────────────────────────────────

def zip_bytes(files: list[tuple[str, bytes]]) -> bytes:
    """Deflated, and written in the order given so the README is opened first."""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, data in files:
            archive.writestr(path, data)
    return buf.getvalue()


def build(state: dict, store_name: str, assets: dict) -> tuple[str, bytes]:
    """
    The package, from the workspace state and the assets already fetched.

    Pure: no database, no network, no clock beyond the README's timestamp. The
    fetching lives in `collect_assets` so this — the part that decides what the
    owner actually receives — can be tested exactly as he will receive it.

    `assets` = {"ad_png": bytes|None, "labels": [(name, png)],
                "sheet_pdf": bytes|None, "platform": dict|None,
                "notes": [str]}
    """
    summary = state.get("context", {}).get("summary", {})
    folder = slug(summary.get("campaign") or "", "campaign")

    included: list[str] = ["campaign-summary.pdf — the brief, ready to print"]
    missing: list[str] = list(assets.get("notes") or [])
    files: list[tuple[str, bytes]] = []

    ad_png = assets.get("ad_png")
    if ad_png:
        files.append((f"{folder}/ad/advertisement.png", ad_png))
        included.append("ad/advertisement.png — the finished advertisement")
    else:
        missing.append("The advertisement — generate one in the campaign workspace.")

    labels = assets.get("labels") or []
    for i, (name, png) in enumerate(labels, start=1):
        files.append((f"{folder}/labels/{i:02d}-{slug(name, 'label')}.png", png))
    if labels:
        included.append(f"labels/ — {len(labels)} shelf label(s) at print resolution")
    else:
        missing.append("Shelf labels — make them in Label Studio and they land here.")

    sheet = assets.get("sheet_pdf")
    if sheet:
        files.append((f"{folder}/labels/print-sheet.pdf", sheet))
        included.append("labels/print-sheet.pdf — print, then cut")

    text_files = copy_files(state.get("copy") or {})
    text_files += platform_copy_files(assets.get("platform"))
    for path, text in text_files:
        files.append((f"{folder}/{path}", text.encode("utf-8")))
    if text_files:
        included.append(f"copy/ — {len(text_files)} text file(s), ready to paste")
    else:
        missing.append("Campaign copy — none written yet.")

    pdf = summary_pdf(state, store_name, ad_png, len(labels))

    # README first, summary second: unpacked, they sort to the top of the folder.
    files = ([(f"{folder}/README.txt",
               readme(state, store_name, included, missing).encode("utf-8")),
              (f"{folder}/campaign-summary.pdf", pdf)] + files)

    return f"{folder}.zip", zip_bytes(files)


async def collect_assets(strategy_id, store_id, db) -> dict:
    """
    Fetch the real assets. The only part of this module that touches the world.

    Every fetch is individually guarded: one label that will not render, or an
    ad image lost to a redeploy, must not deny the owner the rest of his own
    campaign. What failed is recorded in `notes` and printed in the README.
    """
    from sqlalchemy import select

    from app.models.ad_creative import AdCreative
    from app.services import label_design_service as LABELS
    from app.services.shelf_label_renderer import render_label, render_sheet
    from app.services.storage_service import fetch_image

    assets: dict = {"ad_png": None, "labels": [], "sheet_pdf": None,
                    "platform": None, "notes": []}

    creative = (await db.execute(
        select(AdCreative)
        .where(AdCreative.strategy_id == strategy_id,
               AdCreative.store_id == store_id)
        .order_by(AdCreative.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()

    if creative is not None:
        assets["platform"] = {
            field: getattr(creative, field, "") for field, _ in PLATFORM_FILES
        }
        # The composed ad (exact prices stamped on) is the one he would post.
        url = creative.final_image_url or creative.image_url
        try:
            assets["ad_png"] = await fetch_image(url)
        except Exception:  # noqa: BLE001
            logger.warning("Could not read the ad image for the package", exc_info=True)
            assets["notes"].append(
                "The advertisement image could not be read — regenerate it in the "
                "Ad Creator and download again.")

    rows = await LABELS.list_labels(store_id, db, strategy_id)
    specs = []
    for row in rows:
        try:
            assets["labels"].append((row.name, await render_label(row.design_json)))
            specs.append(row.design_json)
        except Exception:  # noqa: BLE001
            logger.warning("Could not render label %s for the package", row.id,
                           exc_info=True)
            assets["notes"].append(f'The label "{row.name}" could not be rendered.')

    if specs:
        try:
            assets["sheet_pdf"] = await render_sheet(specs, per_page=4, page_key="a4")
        except Exception:  # noqa: BLE001
            logger.warning("Could not build the print sheet", exc_info=True)
            assets["notes"].append("The printable label sheet could not be built.")

    return assets
