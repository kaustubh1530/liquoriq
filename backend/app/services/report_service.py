"""
services/report_service.py — Weekly growth report builder and sender

This is the core of Phase 9. For every active store with sales data:
  1. Pulls KPI summary, top 3 and bottom 3 products from analytics_service
  2. Calls GPT-4o to write a 2-3 sentence human-readable narrative
  3. Renders a polished HTML email
  4. Sends it to the store owner via email_service

Called by:
  - scheduler.py  → automatically every Monday at 8am
  - routes/reports.py → manually via POST /reports/send-weekly (for testing)
"""

import logging
import math
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.store import Store
from app.models.user import User
from app.services.analytics_service import (
    get_summary,
    get_top_products,
    get_slow_products,
)
from app.services.openai_service import generate_json_response
from app.services.email_service import send_html_email

logger = logging.getLogger(__name__)


# ─── NaN sanitizer ────────────────────────────────────────────────────────────

def _safe_float(val, default: float = 0.0) -> float:
    """Return 0.0 if val is None or NaN (happens when CSV has no price column)."""
    if val is None:
        return default
    try:
        f = float(val)
        return default if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return default


def _sanitize_summary(summary: dict) -> dict:
    for key in ("total_revenue", "average_order_value", "total_units"):
        summary[key] = _safe_float(summary.get(key))
    return summary


def _sanitize_products(products: list[dict]) -> list[dict]:
    for p in products:
        p["total_revenue"] = _safe_float(p.get("total_revenue"))
    return products


# ─── AI narrative generator ────────────────────────────────────────────────────

async def _generate_narrative(
    store_name: str,
    summary: dict,
    top_products: list[dict],
    slow_products: list[dict],
) -> str:
    """
    Ask GPT-4o to write a 2-3 sentence growth narrative for the email.
    Returns plain text (not JSON this time — we use a simple wrapper).
    """
    system = (
        "You are a friendly business analyst writing a brief weekly summary "
        "for a small liquor store owner. Be encouraging, specific, and actionable. "
        "Respond with JSON: {\"narrative\": \"your 2-3 sentence text here\"}"
    )

    top_names  = [p["product_name"] for p in top_products[:3]]
    slow_names = [p["product_name"] for p in slow_products[:3]]

    user = f"""
Store: {store_name}
This week's data:
- Total revenue: ${summary['total_revenue']:.2f}
- Total orders: {summary['total_orders']}
- Top channel: {summary.get('top_channel', 'N/A')}
- Top products: {', '.join(top_names) if top_names else 'none yet'}
- Slow-moving products: {', '.join(slow_names) if slow_names else 'none yet'}

Write a 2-3 sentence weekly growth summary. Mention what's working, and give
one specific action about the slow-moving products.
"""
    try:
        result = await generate_json_response(system, user)
        return result.get("narrative", "Great work this week! Keep an eye on your slow movers.")
    except Exception as e:
        logger.warning("AI narrative generation failed: %s", e)
        return "Your weekly report is ready. Check the highlights below to guide this week's decisions."


# ─── HTML email template ───────────────────────────────────────────────────────

def _render_email_html(
    store_name: str,
    owner_name: str,
    summary: dict,
    top_products: list[dict],
    slow_products: list[dict],
    narrative: str,
    report_date: str,
) -> str:
    """Render a clean, mobile-friendly HTML email."""

    def product_rows(products: list[dict]) -> str:
        if not products:
            return "<tr><td colspan='3' style='color:#9ca3af;padding:8px 0'>No data yet</td></tr>"
        rows = ""
        for p in products:
            rows += f"""
            <tr>
              <td style="padding:8px 0;border-bottom:1px solid #f3f4f6;font-size:14px;color:#111827">
                {p['product_name']}
              </td>
              <td style="padding:8px 0;border-bottom:1px solid #f3f4f6;font-size:14px;color:#6b7280;text-align:center">
                {p.get('category') or '—'}
              </td>
              <td style="padding:8px 0;border-bottom:1px solid #f3f4f6;font-size:14px;font-weight:600;text-align:right;color:#111827">
                ${p['total_revenue']:.2f}
              </td>
            </tr>"""
        return rows

    date_range = ""
    if summary.get("date_from") and summary.get("date_to"):
        date_range = f"{summary['date_from']} → {summary['date_to']}"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>LiquorIQ Weekly Report</title>
</head>
<body style="margin:0;padding:0;background:#f9fafb;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f9fafb;padding:32px 16px">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%">

        <!-- Header -->
        <tr>
          <td style="background:#e8a020;border-radius:16px 16px 0 0;padding:32px;text-align:center">
            <p style="margin:0;font-size:28px">🥃</p>
            <h1 style="margin:8px 0 4px;color:#fff;font-size:22px;font-weight:700">LiquorIQ</h1>
            <p style="margin:0;color:rgba(255,255,255,0.85);font-size:14px">Weekly Growth Report · {report_date}</p>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="background:#fff;padding:32px;border-left:1px solid #f3f4f6;border-right:1px solid #f3f4f6">

            <p style="margin:0 0 8px;font-size:16px;color:#111827">Hi {owner_name},</p>
            <p style="margin:0 0 24px;font-size:14px;color:#6b7280">
              Here's your weekly performance summary for <strong>{store_name}</strong>.
              {f'Data period: {date_range}.' if date_range else ''}
            </p>

            <!-- AI Narrative -->
            <div style="background:#fdf4e7;border-left:4px solid #e8a020;border-radius:0 8px 8px 0;padding:16px;margin-bottom:28px">
              <p style="margin:0;font-size:14px;color:#7a4a05;line-height:1.6">{narrative}</p>
            </div>

            <!-- KPI Cards -->
            <h2 style="margin:0 0 16px;font-size:15px;font-weight:600;color:#374151;text-transform:uppercase;letter-spacing:0.05em">
              This Week's Numbers
            </h2>
            <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:28px">
              <tr>
                <td style="width:25%;padding:16px;background:#f9fafb;border-radius:12px;text-align:center">
                  <p style="margin:0;font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:0.05em">Revenue</p>
                  <p style="margin:4px 0 0;font-size:22px;font-weight:700;color:#111827">${summary['total_revenue']:.0f}</p>
                </td>
                <td style="width:4%"></td>
                <td style="width:25%;padding:16px;background:#f9fafb;border-radius:12px;text-align:center">
                  <p style="margin:0;font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:0.05em">Orders</p>
                  <p style="margin:4px 0 0;font-size:22px;font-weight:700;color:#111827">{summary['total_orders']}</p>
                </td>
                <td style="width:4%"></td>
                <td style="width:25%;padding:16px;background:#f9fafb;border-radius:12px;text-align:center">
                  <p style="margin:0;font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:0.05em">Units Sold</p>
                  <p style="margin:4px 0 0;font-size:22px;font-weight:700;color:#111827">{summary['total_units']:.0f}</p>
                </td>
                <td style="width:4%"></td>
                <td style="width:25%;padding:16px;background:#f9fafb;border-radius:12px;text-align:center">
                  <p style="margin:0;font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:0.05em">Avg Order</p>
                  <p style="margin:4px 0 0;font-size:22px;font-weight:700;color:#111827">${summary['average_order_value']:.0f}</p>
                </td>
              </tr>
            </table>

            <!-- Top Products -->
            <h2 style="margin:0 0 12px;font-size:15px;font-weight:600;color:#374151;text-transform:uppercase;letter-spacing:0.05em">
              🏆 Top Products
            </h2>
            <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:28px">
              <tr>
                <th style="text-align:left;font-size:11px;color:#9ca3af;padding-bottom:8px;font-weight:500">Product</th>
                <th style="text-align:center;font-size:11px;color:#9ca3af;padding-bottom:8px;font-weight:500">Category</th>
                <th style="text-align:right;font-size:11px;color:#9ca3af;padding-bottom:8px;font-weight:500">Revenue</th>
              </tr>
              {product_rows(top_products[:5])}
            </table>

            <!-- Slow Movers -->
            <h2 style="margin:0 0 8px;font-size:15px;font-weight:600;color:#374151;text-transform:uppercase;letter-spacing:0.05em">
              ⚠️ Needs Attention
            </h2>
            <p style="margin:0 0 12px;font-size:13px;color:#6b7280">
              These products have the lowest sales — consider running a promotion.
            </p>
            <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:32px">
              <tr>
                <th style="text-align:left;font-size:11px;color:#9ca3af;padding-bottom:8px;font-weight:500">Product</th>
                <th style="text-align:center;font-size:11px;color:#9ca3af;padding-bottom:8px;font-weight:500">Category</th>
                <th style="text-align:right;font-size:11px;color:#9ca3af;padding-bottom:8px;font-weight:500">Revenue</th>
              </tr>
              {product_rows(slow_products[:5])}
            </table>

            <!-- CTA -->
            <div style="text-align:center">
              <a href="http://localhost:5173/dashboard"
                 style="display:inline-block;background:#e8a020;color:#fff;font-weight:600;font-size:14px;padding:14px 32px;border-radius:12px;text-decoration:none">
                View Full Dashboard →
              </a>
            </div>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background:#f3f4f6;border-radius:0 0 16px 16px;padding:20px;text-align:center">
            <p style="margin:0;font-size:12px;color:#9ca3af">
              LiquorIQ · AI-powered growth intelligence for liquor stores<br>
              You're receiving this because you're a LiquorIQ store owner.
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


# ─── Main report sender ────────────────────────────────────────────────────────

async def send_weekly_report_for_store(
    store_id: uuid.UUID,
    db: AsyncSession,
) -> dict:
    """
    Build and send the weekly report for one store.
    Returns a status dict: {store_name, email, status, error?}
    """
    # Load store + owner
    result = await db.execute(
        select(Store, User)
        .join(User, Store.owner_id == User.id)
        .where(Store.id == store_id)
    )
    row = result.one_or_none()
    if not row:
        return {"store_id": str(store_id), "status": "skipped", "error": "Store not found"}

    store, owner = row

    try:
        # Gather analytics
        summary      = _sanitize_summary(await get_summary(store_id=store_id, db=db))
        top_products = _sanitize_products(await get_top_products(store_id=store_id, db=db, limit=5))
        slow_products = _sanitize_products(await get_slow_products(store_id=store_id, db=db, limit=5))

        if summary["total_orders"] == 0:
            return {
                "store_name": store.name,
                "email": owner.email,
                "status": "skipped",
                "error": "No sales data yet",
            }

        # Generate AI narrative
        narrative = await _generate_narrative(
            store_name=store.name,
            summary=summary,
            top_products=top_products,
            slow_products=slow_products,
        )

        # Render HTML email
        report_date = datetime.now(timezone.utc).strftime("%B %d, %Y")
        html = _render_email_html(
            store_name=store.name,
            owner_name=owner.full_name,
            summary=summary,
            top_products=top_products,
            slow_products=slow_products,
            narrative=narrative,
            report_date=report_date,
        )

        # Send email
        await send_html_email(
            to_email=owner.email,
            subject=f"🥃 {store.name} — Your Weekly Growth Report ({report_date})",
            html_body=html,
        )

        return {"store_name": store.name, "email": owner.email, "status": "sent"}

    except Exception as e:
        logger.error("Failed to send report for store %s: %s", store.name, e)
        return {"store_name": store.name, "email": owner.email, "status": "failed", "error": str(e)}


async def send_all_weekly_reports() -> list[dict]:
    """
    Send weekly reports to ALL active stores.
    Called by the scheduler every Monday at 8am.
    Opens its own DB session (scheduler runs outside request context).
    """
    logger.info("Starting weekly report run for all stores...")
    results = []

    async with AsyncSessionLocal() as db:
        store_result = await db.execute(
            select(Store).where(Store.is_active == True)  # noqa: E712
        )
        stores = store_result.scalars().all()
        logger.info("Found %d active stores", len(stores))

        for store in stores:
            result = await send_weekly_report_for_store(
                store_id=store.id,
                db=db,
            )
            results.append(result)
            logger.info("Report result: %s", result)

    logger.info("Weekly report run complete: %d stores processed", len(results))
    return results
