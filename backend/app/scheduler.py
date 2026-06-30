"""
scheduler.py — APScheduler configuration for LiquorIQ

Runs background jobs on a schedule without needing Celery or Redis.
For a small SaaS with <100 stores, APScheduler is the right choice —
no infrastructure overhead, runs inside the FastAPI process.

Current jobs:
  weekly_growth_report — every Monday at 8:00 AM UTC

Started in main.py via FastAPI's lifespan context manager.
"""

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

# Module-level scheduler instance — started once on app startup
scheduler = AsyncIOScheduler(timezone="UTC")


def _schedule_weekly_report() -> None:
    """Register the weekly report job."""
    from app.services.report_service import send_all_weekly_reports

    scheduler.add_job(
        send_all_weekly_reports,
        trigger=CronTrigger(
            day_of_week="mon",   # Every Monday
            hour=8,              # 8:00 AM UTC
            minute=0,
        ),
        id="weekly_growth_report",
        name="Send weekly growth reports to all stores",
        replace_existing=True,
        misfire_grace_time=3600,  # Run even if delayed by up to 1 hour
    )
    logger.info("Scheduled: weekly_growth_report — every Monday at 08:00 UTC")


def start_scheduler() -> None:
    """Start the scheduler and register all jobs. Called on app startup."""
    _schedule_weekly_report()
    scheduler.start()
    logger.info("APScheduler started with %d job(s)", len(scheduler.get_jobs()))


def stop_scheduler() -> None:
    """Gracefully shut down the scheduler. Called on app shutdown."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")
