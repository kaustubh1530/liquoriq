"""
tests/test_design_plan.py — MODULE 1: AI AD CREATOR

Covers the design plan's contract: it validates art direction for ONE finished
advertisement, gates product details, and NEVER asks the model for text or badges.
"""

from app.services import design_plan as dp


def _plan(**over):
    base = {
        "headline": "LABOR DAY SALE", "subheadline": "", "visual_theme": "summer bbq",
        "palette": "red white blue", "typography_style": "bold", "product_placement": "right",
        "product_details": [], "background": "backyard", "lighting": "golden hour",
        "composition": "grid",
    }
    base.update(over)
    return base


# ── Scrubbing + caps ──────────────────────────────────────────────────────────

def test_forbidden_internal_terms_scrubbed_everywhere():
    plan = _plan(headline="Big Sale (70% margin)", subheadline="Huge profit for us",
                 product_details=["Great markup", "Smooth finish"])
    out = dp.validate_design_plan(plan, "Booker's Bourbon", "$29.99", owner_wants_details=True)
    assert "margin" not in out["headline"].lower()
    assert out["subheadline"] == "" or "profit" not in out["subheadline"].lower()
    joined = " ".join(out["product_details"]).lower()
    assert "markup" not in joined
    assert "smooth finish" in joined  # legit benefit kept


def test_length_caps_and_offer_is_owner_controlled():
    plan = _plan(headline="X" * 100)
    out = dp.validate_design_plan(plan, "Vodka", "$24.99")
    assert len(out["headline"]) <= dp.HEADLINE_MAX
    assert out["offer_text"] == "$24.99"   # owner offer, not from the AI


# ── Product-detail gating (the new campaign-type rule) ────────────────────────

def test_details_suppressed_for_standard_campaign():
    plan = _plan(product_details=["Smooth finish", "Great for gifting"])
    out = dp.validate_design_plan(plan, "Vodka", "$24.99", campaign_type="standard")
    assert out["product_details"] == []   # clean and minimal


def test_details_shown_for_product_led_campaign_types():
    for ctype in ("new_arrival", "product_spotlight", "premium_collection", "limited_edition"):
        plan = _plan(product_details=["Smooth finish"])
        out = dp.validate_design_plan(plan, "Vodka", "$24.99", campaign_type=ctype)
        assert out["product_details"] == ["Smooth finish"], ctype


def test_owner_opt_in_shows_details_even_on_standard():
    plan = _plan(product_details=["Smooth finish"])
    out = dp.validate_design_plan(plan, "Vodka", "$24.99",
                                  campaign_type="standard", owner_wants_details=True)
    assert out["product_details"] == ["Smooth finish"]


def test_show_product_details_helper():
    assert dp.show_product_details("standard", False) is False
    assert dp.show_product_details("standard", True) is True
    assert dp.show_product_details("new_arrival", False) is True
    assert dp.show_product_details(None, False) is False


def test_details_capped_deduped_and_no_product_name():
    plan = _plan(product_details=["Smooth", "Smooth", "Crisp", "Bold", "Booker's Bourbon 750ml"])
    out = dp.validate_design_plan(plan, "Booker's Bourbon", "$29.99", owner_wants_details=True)
    assert len(out["product_details"]) <= dp.DETAIL_MAX_ITEMS
    assert len(out["product_details"]) == len(set(b.lower() for b in out["product_details"]))
    assert all("booker" not in b.lower() for b in out["product_details"])


# ── Fact grounding ────────────────────────────────────────────────────────────

def test_unsupported_factual_claims_dropped_without_facts():
    plan = _plan(product_details=["90 proof", "Aged 12 years", "Rich flavor"])
    out = dp.validate_design_plan(plan, "Whiskey", "$40", product_facts=None,
                                  owner_wants_details=True)
    joined = " ".join(out["product_details"]).lower()
    assert "proof" not in joined and "aged" not in joined
    assert "rich flavor" in joined


def test_supported_claim_kept_with_confirmed_facts():
    plan = _plan(product_details=["90 proof", "Rich flavor"])
    out = dp.validate_design_plan(plan, "Whiskey", "$40", product_facts={"proof": "90 proof"},
                                  owner_wants_details=True)
    assert "proof" in " ".join(out["product_details"]).lower()


# ── The image prompt: scene only, no text, no badges ──────────────────────────

def test_image_prompt_forbids_all_text():
    plan = dp.validate_design_plan(_plan(), "Vodka", "$24.99")
    prompt = dp.compose_image_prompt(plan, "Classy Corks").lower()
    assert "no text" in prompt
    assert "$24.99" not in prompt          # the price is never given to the model
    assert "classy corks" not in prompt    # nor is the store name


def test_image_prompt_forbids_badges_and_stickers():
    """Badges belong to the Label Studio — the generator must never draw them."""
    plan = dp.validate_design_plan(_plan(), "Vodka", "$24.99")
    prompt = dp.compose_image_prompt(plan, "Store").lower()
    for banned in ("badge", "sticker", "ribbon", "price tag", "coupon", "starburst", "seal"):
        assert banned in prompt, f"prompt should explicitly forbid {banned!r}"


def test_image_prompt_keeps_background_rich():
    plan = dp.validate_design_plan(_plan(), "Vodka", "$24.99")
    prompt = dp.compose_image_prompt(plan, "Store").lower()
    assert "rich" in prompt and "not a plain" in prompt


# ── The hand-off to the deterministic text renderer ───────────────────────────

def test_ad_text_spec_carries_exact_price_and_store():
    plan = dp.validate_design_plan(_plan(), "Vodka", "$24.99")
    spec = dp.ad_text_spec(plan, "Classy Corks")
    assert spec["price"] == "$24.99"        # exactly what the owner typed
    assert spec["store_name"] == "Classy Corks"
    assert spec["headline"]
    assert spec["details"] == []            # standard campaign → minimal


def test_ad_text_spec_has_no_badge_fields():
    """The renderer must not be handed anything badge-shaped (that's module 2)."""
    plan = dp.validate_design_plan(_plan(), "Vodka", "$24.99")
    spec = dp.ad_text_spec(plan, "Store")
    assert set(spec) == {"eyebrow", "headline", "subheadline", "price",
                         "price_is_amount", "product", "store_name",
                         "details", "accent"}
    for banned in ("badge", "badges", "sticker", "ribbon", "shape", "labels"):
        assert banned not in spec


def test_ai_badge_texts_are_discarded():
    """Even if the model returns badges, the validated plan drops them."""
    plan = _plan(badge_texts=["LIMITED EDITION", "SAVE $10"])
    out = dp.validate_design_plan(plan, "Vodka", "$24.99", owner_wants_details=True)
    assert "badge_texts" not in out
