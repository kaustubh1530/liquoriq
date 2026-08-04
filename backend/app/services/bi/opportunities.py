"""
services/bi/opportunities.py — PHASE 22: GROWTH OPPORTUNITY ENGINE

Seven deterministic detectors. Each looks at the enriched product metrics (plus
holidays, customer segments and past campaigns where relevant) and returns
opportunities carrying a DOLLAR value and a CONFIDENCE.

RANKING: value_score × confidence_weight. A large but shaky estimate must not
outrank a smaller, well-evidenced one — and the formula is shown in the UI so
the owner can see why something is at the top instead of trusting a black box.

Every number here is arithmetic on the store's own data plus a named assumption
from assumptions.py. No AI. GPT is only asked to phrase the result, elsewhere.
"""

from app.services.bi import assumptions as A
from app.services.bi import planning as PLAN
from app.services.bi import seasonality as SEASON

# Detector identifiers, in the order they're evaluated.
TYPES = [
    "reorder", "clearance", "seasonal", "bundle",
    "premium_upsell", "winback", "campaign_repeat",
]


def _opportunity(
    kind, title, value, confidence, reason, evidence, action, route,
    products=None, expected=None, product_values=None, estimated=True,
):
    """
    One opportunity, in the shape the Action Center and UI expect.

    `product_values` maps product name → the value THIS opportunity would get
    from that product. It exists so a product can be assigned to exactly one
    opportunity: Clearance and Seasonal previously named the same 18 of 20
    products, and the headline total added both, presenting a choice between
    alternatives as a sum. See `allocate_exclusively`.

    `estimated` marks a figure that depends on an assumed rate rather than
    being measured outright, so the UI can never show it as a fact.
    """
    weight = A.CONFIDENCE_WEIGHTS[confidence]
    return {
        "type": kind,
        "title": title,
        "value_score": round(value, 2),
        "confidence": confidence,
        "confidence_reason": reason,
        "confidence_weight": weight,
        "ranked_value": round(value * weight, 2),
        "evidence": evidence,
        "expected_outcome": expected or "",
        "suggested_action": action,
        "route": route,
        "products": products or [],
        "product_values": product_values or {},
        "estimated": estimated,
        **PLAN.timeline_for(kind, evidence),
    }


# ── 1. REORDER — stock-outs and near-stock-outs that were selling ───────────

def detect_reorder(metrics, periods_of_history=1):
    urgent = [m for m in metrics if m["stock_class"] in ("sold_out", "critical", "reorder")
              and m["units_sold"] > 0]
    if not urgent:
        return []
    urgent.sort(key=lambda m: -m["money_at_stake"])

    value = sum(m["money_at_stake"] for m in urgent)
    sold_out = [m for m in urgent if m["stock_class"] == "sold_out"]

    # One period tells us WHAT sold, not whether it sells reliably.
    confidence = "high" if periods_of_history >= A.HIGH_CONFIDENCE_PERIODS else "medium"
    reason = ("velocity confirmed across several uploads"
              if confidence == "high"
              else "based on a single reporting period — upload again to confirm the trend")

    return [_opportunity(
        "reorder",
        f"Reorder {len(urgent)} products before you lose more sales",
        value, confidence, reason,
        evidence={
            "products_out_of_stock": len(sold_out),
            "products_running_low": len(urgent) - len(sold_out),
            "weekly_sales_at_risk": round(sum(m["weekly_velocity"] * m["unit_price"]
                                              for m in urgent), 2),
            "horizon_weeks": A.REORDER_HORIZON_WEEKS,
            "top_items": [m["product_name"] for m in urgent[:5]],
        },
        expected=(f"Recover about ${value:,.0f} of sales over the next "
                  f"{A.REORDER_HORIZON_WEEKS:.0f} weeks"),
        action=f"Reorder these {len(urgent)} products from your supplier",
        route="/dashboard?focus=reorder",
        products=[m["product_name"] for m in urgent[:20]],
        product_values={m["product_name"]: m["money_at_stake"] for m in urgent},
    )]


# ── 2. CLEARANCE — cash frozen in dead, sleeping and overstocked goods ───────

def detect_clearance(metrics, period_revenue=0.0, period_days=30):
    stuck = [m for m in metrics if m["stock_class"] in ("dead", "sleeping", "overstock")
             and m["cash_frozen"] > 0]
    if not stuck:
        return []
    stuck.sort(key=lambda m: -m["cash_frozen"])

    frozen = sum(m["cash_frozen"] for m in stuck)
    recoverable = frozen * A.CLEARANCE_RECOVERY_RATE
    sleeping = [m for m in stuck if m["stock_class"] == "sleeping"]

    # Sized against the store's own revenue. $132,396 is two months of this
    # shop's ENTIRE takings — "do this now" was never achievable.
    plan = PLAN.clearance_phases(stuck, period_revenue, period_days)

    return [_opportunity(
        "clearance",
        f"${frozen:,.0f} is frozen in {len(stuck)} slow-moving products",
        recoverable, "high",
        "the frozen cash is measured from your own stock and sales; the "
        f"{A.CLEARANCE_RECOVERY_RATE:.0%} recovery rate is an assumption",
        evidence={
            "cash_frozen_retail": round(frozen, 2),
            "products": len(stuck),
            "sleeping_over_a_year": len(sleeping),
            "sleeping_cash": round(sum(m["cash_frozen"] for m in sleeping), 2),
            "assumed_recovery_rate": A.CLEARANCE_RECOVERY_RATE,
            "realistic_months_to_clear": plan["months_to_clear"],
            "monthly_clearance_capacity": plan["monthly_capacity"],
            "top_items": [f"{m['product_name']} (${m['cash_frozen']:,.0f})" for m in stuck[:5]],
        },
        expected=(f"Free up roughly ${recoverable:,.0f} over about "
                  f"{plan['months_to_clear']} months at a "
                  f"{A.CLEARANCE_RECOVERY_RATE:.0%} clearance rate"),
        action="Run a clearance campaign on the highest-value slow movers",
        route="/ai?focus=clearance",
        products=[m["product_name"] for m in stuck[:20]],
        product_values={m["product_name"]: m["cash_frozen"] * A.CLEARANCE_RECOVERY_RATE
                        for m in stuck},
    ) | {"plan": plan}]


# ── 3. SEASONAL — an upcoming holiday against what's actually in stock ───────

def detect_seasonal(metrics, holidays, category_hints=None):
    """
    holidays: [{key, name, date, days_away}] from holiday_calendar.

    REWRITTEN FOR RELEVANCE. This previously scoped every product the store
    held — $310,591, 99% of the entire inventory — and multiplied it by a flat
    15%. Nobody buys Cognac for a barbecue. Scope now comes from
    seasonality.py, which names the categories that actually move for each
    holiday and gives every qualifying product a reason.

    The value is also computed differently. It used to be 15% of the RETAIL
    VALUE OF SHELF STOCK, which rewarded holding dead inventory — the more you
    couldn't sell, the bigger your "opportunity". It is now a lift on what
    those products ACTUALLY SOLD, capped by the stock on hand.
    """
    if not holidays:
        return []
    out = []

    for holiday in holidays[:3]:
        days_away = holiday.get("days_away")
        if days_away is None or not (0 <= days_away <= 45):
            continue

        name = holiday.get("name", "the holiday")
        qualified = SEASON.qualify(metrics, holiday.get("key", ""), name)
        if not qualified:
            continue

        uplift = SEASON.expected_uplift(qualified, holiday.get("key", ""))
        if uplift["value"] <= 0:
            continue

        qualified.sort(key=lambda m: -m["revenue"])
        by_category: dict[str, int] = {}
        for m in qualified:
            by_category[m.get("category") or "Other"] = \
                by_category.get(m.get("category") or "Other", 0) + 1

        out.append(_opportunity(
            "seasonal",
            f"{name} is {days_away} days away",
            uplift["value"], "medium",
            f"scoped to {uplift['products']} relevant products; the "
            f"{uplift['lift_rate']:.0%} uplift is an industry assumption, not "
            f"measured from your own past holidays",
            evidence={
                "holiday": name,
                "days_away": days_away,
                "relevant_categories": uplift["categories"] or ["keyword matches only"],
                "products_in_scope": uplift["products"],
                "their_sales_last_period": uplift["base_revenue"],
                "assumed_uplift_rate": uplift["lift_rate"],
                "stock_available": uplift["stock_value"],
                "capped_by_stock": uplift["capped_by_stock"],
                "why_these_products": uplift["note"],
                "top_items": [
                    f"{m['product_name']} — {m['qualified_because']}"
                    for m in qualified[:5]
                ],
                "products_by_category": by_category,
            },
            expected=(f"Around ${uplift['value']:,.0f} of additional sales — "
                      f"{uplift['lift_rate']:.0%} on the ${uplift['base_revenue']:,.0f} "
                      f"these products already sell"),
            action=f"Build a {name} campaign around these {uplift['products']} products",
            route="/ai?focus=seasonal",
            products=[m["product_name"] for m in qualified[:20]],
            product_values={
                m["product_name"]: m["revenue"] * uplift["lift_rate"] for m in qualified
            },
        ))
    return out


# ── 4. BUNDLE — pair a slow mover with a fast one in the same category ───────

def detect_bundle(metrics):
    """
    The classic move: attach something that isn't selling to something that is.
    We only pair WITHIN a category, because that's where the pairing reads as
    natural to a shopper (a slow bourbon next to a fast bourbon).
    """
    by_category: dict[str, list] = {}
    for m in metrics:
        if m.get("category") and m["stock_class"] != "negative":
            by_category.setdefault(m["category"], []).append(m)

    pairs = []
    for category, items in by_category.items():
        fast = [m for m in items if m["stock_class"] in ("healthy", "critical", "reorder")
                and m["units_sold"] > 0]
        slow = [m for m in items if m["stock_class"] in ("sleeping", "overstock")
                and m["cash_frozen"] > 0]
        if not fast or not slow:
            continue
        fast.sort(key=lambda m: -m["units_sold"])
        slow.sort(key=lambda m: -m["cash_frozen"])
        anchor, drag = fast[0], slow[0]
        value = anchor["units_sold"] * A.BUNDLE_ATTACH_RATE * drag["unit_price"]
        if value > 0:
            pairs.append((value, category, anchor, drag))

    if not pairs:
        return []
    pairs.sort(key=lambda p: -p[0])
    total = sum(p[0] for p in pairs)

    return [_opportunity(
        "bundle",
        f"Bundle slow stock with your best sellers in {len(pairs)} categories",
        total, "low",
        "attach rate is an industry assumption; you have no basket-level data yet",
        evidence={
            "pairs": [
                {"category": c, "anchor": a["product_name"], "anchor_units": a["units_sold"],
                 "slow_item": d["product_name"], "slow_cash": d["cash_frozen"],
                 "value": round(v, 2)}
                for v, c, a, d in pairs[:5]
            ],
            "attach_rate": A.BUNDLE_ATTACH_RATE,
        },
        expected=f"Roughly ${total:,.0f} of extra sales from attaching slow stock",
        action="Create bundle shelf tags pairing these products",
        route="/labels?focus=bundle",
        products=[d["product_name"] for _, _, _, d in pairs[:10]],
        product_values={d["product_name"]: v for v, _, _, d in pairs},
    )]


# ── 5. PREMIUM UPSELL — same brand, bigger or pricier format in stock ────────

def detect_premium_upsell(metrics, brands):
    """
    brands: {product_name: brand}. Where one brand appears at two price points
    and the cheaper one sells well, prompting the trade-up at the shelf is close
    to free money — the stock is already there.
    """
    groups: dict[str, list] = {}
    for m in metrics:
        brand = brands.get(m["product_name"])
        if brand and m["stock_class"] != "negative":
            groups.setdefault(brand, []).append(m)

    candidates = []
    for brand, items in groups.items():
        if len(items) < 2:
            continue
        items.sort(key=lambda m: m["unit_price"])
        cheap, premium = items[0], items[-1]
        gap = premium["unit_price"] - cheap["unit_price"]
        if gap <= 0 or cheap["units_sold"] <= 0 or premium["stock"] <= 0:
            continue
        value = cheap["units_sold"] * A.UPSELL_CONVERSION_RATE * gap
        if value > 0:
            candidates.append((value, brand, cheap, premium))

    if not candidates:
        return []
    candidates.sort(key=lambda c: -c[0])
    total = sum(c[0] for c in candidates)

    return [_opportunity(
        "premium_upsell",
        f"Trade customers up on {len(candidates)} brands you already stock",
        total, "medium",
        "price gaps are real; the conversion rate is an assumption",
        evidence={
            "ladders": [
                {"brand": b, "from": c["product_name"], "from_price": c["unit_price"],
                 "to": p["product_name"], "to_price": p["unit_price"],
                 "units_at_entry": c["units_sold"], "value": round(v, 2)}
                for v, b, c, p in candidates[:5]
            ],
            "conversion_rate": A.UPSELL_CONVERSION_RATE,
        },
        expected=f"About ${total:,.0f} of extra margin from the same footfall",
        action="Put 'trade up' shelf tags beside the entry-level size",
        route="/labels?focus=upsell",
        products=[p["product_name"] for _, _, _, p in candidates[:10]],
        product_values={p["product_name"]: v for v, _, _, p in candidates},
    )]


# ── 6. WIN-BACK — lapsed customers from RFM ─────────────────────────────────

def detect_winback(segments):
    """segments: {segment_name: {count, avg_spend}} from the RFM engine."""
    if not segments:
        return []
    lapsed = {k: v for k, v in segments.items()
              if k in ("At Risk", "Inactive") and (v or {}).get("count", 0) > 0}
    if not lapsed:
        return []

    total_people = sum(v["count"] for v in lapsed.values())
    value = sum(v["count"] * A.WINBACK_RESPONSE_RATE * (v.get("avg_spend") or 0.0)
                for v in lapsed.values())
    if value <= 0:
        return []

    return [_opportunity(
        "winback",
        f"Win back {total_people} lapsed customers",
        value, "medium",
        "segment sizes and past spend are real; the response rate is an assumption",
        evidence={
            "segments": {k: {"customers": v["count"], "avg_spend": round(v.get("avg_spend") or 0, 2)}
                         for k, v in lapsed.items()},
            "total_customers": total_people,
            "response_rate": A.WINBACK_RESPONSE_RATE,
        },
        expected=f"Roughly ${value:,.0f} from customers who already know you",
        action="Send a win-back offer to the At Risk and Inactive segments",
        route="/ai?focus=winback",
    )]


# ── 7. CAMPAIGN REPEAT — a past campaign that measurably worked ──────────────

def detect_campaign_repeat(campaigns):
    """
    campaigns: [{title, lift_revenue, days_since, strategy_id}].
    The strongest evidence in the whole engine: it already worked HERE.
    """
    winners = [c for c in (campaigns or [])
               if (c.get("lift_revenue") or 0) > 0 and (c.get("days_since") or 0) >= 21]
    if not winners:
        return []
    winners.sort(key=lambda c: -(c["lift_revenue"] or 0))
    best = winners[0]
    value = best["lift_revenue"]

    return [_opportunity(
        "campaign_repeat",
        f"Repeat '{best.get('title', 'your best campaign')}' — it worked",
        value, "high",
        "measured lift from your own sales data, not an estimate",
        evidence={
            "campaign": best.get("title"),
            "measured_lift": round(value, 2),
            "days_since_it_ran": best.get("days_since"),
            "other_winners": len(winners) - 1,
        },
        expected=f"It previously produced ${value:,.0f} of measured lift",
        action="Run this campaign again",
        route=f"/ai?repeat={best.get('strategy_id', '')}",
    )]


# ── Orchestration ────────────────────────────────────────────────────────────

# Opportunities that are about CUSTOMERS, not stock. A win-back mailing and a
# clearance can both run on the same bottle without conflict, so these are
# exempt from exclusive allocation.
CUSTOMER_LED = {"winback", "campaign_repeat"}


def allocate_exclusively(opportunities: list[dict]) -> list[dict]:
    """
    Give every product ONE primary action, and recompute each opportunity from
    only the products it kept.

    WHY THIS EXISTS. Clearance and Seasonal named the same 18 of 20 products
    and the dashboard added their values together: "$191,074 on the table".
    You cannot dump a bottle at 60% clearance AND sell it at a holiday markup —
    those are alternatives, and presenting a choice as a sum overstates the
    total by whatever the overlap is worth.

    Each product goes to whichever opportunity values it most, which is also
    the answer to "what should I do with this bottle?". An opportunity left
    with no products is dropped: a recommendation whose every item is better
    handled elsewhere is not a recommendation.
    """
    contested = [o for o in opportunities if o["type"] not in CUSTOMER_LED]
    exempt = [o for o in opportunities if o["type"] in CUSTOMER_LED]

    # Winner per product. Ties break on confidence weight, then on type name so
    # the outcome is deterministic run to run.
    winner: dict[str, tuple] = {}
    for opportunity in contested:
        for product, value in (opportunity["product_values"] or {}).items():
            key = (float(value or 0.0), opportunity["confidence_weight"], opportunity["type"])
            if product not in winner or key > winner[product][0]:
                winner[product] = (key, opportunity["type"])

    surviving = []
    for opportunity in contested:
        kept = {p: v for p, v in (opportunity["product_values"] or {}).items()
                if winner.get(p, (None, None))[1] == opportunity["type"]}

        # A detector with no per-product breakdown can't be allocated; keep it
        # whole rather than silently zeroing it.
        if not opportunity["product_values"]:
            surviving.append(opportunity)
            continue
        if not kept:
            continue

        lost = len(opportunity["product_values"]) - len(kept)
        value = sum(kept.values())
        weight = opportunity["confidence_weight"]

        opportunity = {
            **opportunity,
            "value_score": round(value, 2),
            "ranked_value": round(value * weight, 2),
            "products": [p for p in opportunity["products"] if p in kept][:20],
            "product_values": {p: round(v, 2) for p, v in kept.items()},
            "products_allocated": len(kept),
            "products_yielded": lost,
        }
        if lost:
            opportunity["allocation_note"] = (
                f"{lost} product{'s' if lost != 1 else ''} moved to a "
                f"higher-value action, so they are not counted twice."
            )
        surviving.append(opportunity)

    return surviving + exempt


def detect_all(
    metrics,
    holidays=None,
    segments=None,
    campaigns=None,
    brands=None,
    periods_of_history=1,
    period_days=30,
):
    """
    Run every detector, give each product one primary action, and return the
    result sorted by ranked value (dollars × confidence weight), highest first.
    """
    period_revenue = sum(m["revenue"] for m in metrics)
    found = []
    found += detect_reorder(metrics, periods_of_history)
    found += detect_clearance(metrics, period_revenue, period_days)
    found += detect_seasonal(metrics, holidays or [])
    found += detect_bundle(metrics)
    found += detect_premium_upsell(metrics, brands or {})
    found += detect_winback(segments or {})
    found += detect_campaign_repeat(campaigns or [])

    found = allocate_exclusively(found)

    found.sort(key=lambda o: -o["ranked_value"])
    for rank, opportunity in enumerate(found, start=1):
        opportunity["rank"] = rank
    return found


def total_value(opportunities) -> dict:
    """
    Headline totals.

    Safe to add ONLY because allocate_exclusively has already given every
    product a single owner. Summing the raw detector output double-counted
    every product that appeared in two opportunities.
    """
    return {
        "raw": round(sum(o["value_score"] for o in opportunities), 2),
        "confidence_adjusted": round(sum(o["ranked_value"] for o in opportunities), 2),
        "count": len(opportunities),
        "basis": (
            "Each product contributes to one opportunity only — its highest-value "
            "action — so these totals are not double-counted. Figures marked as "
            "estimates depend on assumed rates."
        ),
    }
