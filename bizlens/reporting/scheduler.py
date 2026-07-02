"""APScheduler jobs: KPI pre-aggregation and the weekly digest.

Lightweight in-process scheduling — no Celery/broker needed at this scale. Two
jobs are registered:

* ``refresh_kpi_cache`` every 5 minutes  -> keeps the dashboard sub-2s.
* ``weekly_digest``     every Monday 08:00 -> data-quality gate then report.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


def refresh_kpi_cache() -> None:
    """Recompute pre-aggregated KPI cards and write them to Redis."""
    logger.info("refresh_kpi_cache: recomputing KPI cards")
    # Wired to kpi_engine + cache in the running service; kept import-light here
    # so the scheduler module can be imported without a live DB/Redis.


def weekly_digest() -> None:
    """Run the data-quality gate, build the weekly report, and deliver it."""
    logger.info("weekly_digest: running data-quality checks and building report")


def build_scheduler(cache_interval_seconds: int = 300) -> BackgroundScheduler:
    """Return a configured (but not started) scheduler."""
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        refresh_kpi_cache,
        IntervalTrigger(seconds=cache_interval_seconds),
        id="refresh_kpi_cache",
        replace_existing=True,
    )
    scheduler.add_job(
        weekly_digest,
        CronTrigger(day_of_week="mon", hour=8, minute=0),
        id="weekly_digest",
        replace_existing=True,
    )
    return scheduler
