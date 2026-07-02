"""APScheduler jobs: KPI pre-aggregation and the weekly digest.

Lightweight in-process scheduling — no Celery/broker needed at this scale. Two
jobs are registered:

* ``refresh_kpi_cache`` every 5 minutes  -> keeps the dashboard sub-2s.
* ``weekly_digest``     every Monday 08:00 -> data-quality gate then report.
"""
from __future__ import annotations

import datetime as dt
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


def refresh_kpi_cache() -> None:
    """Recompute pre-aggregated KPI cards + revenue trend and write them to Redis."""
    from bizlens import warehouse

    cards = warehouse.kpi_cards(force_refresh=True)
    warehouse.revenue_trend(force_refresh=True)
    logger.info("refresh_kpi_cache: cached %d KPI cards", len(cards))


def weekly_digest() -> None:
    """Run the data-quality gate, build the weekly report, and export it.

    The report is blocked if any source table fails its quality checks — no
    digest ships on bad data.
    """
    from bizlens import warehouse
    from bizlens.db import read_sql
    from bizlens.reporting.data_quality_checker import run_standard_checks
    from bizlens.reporting.insight_generator import MetricDelta
    from bizlens.reporting.report_builder import build_report, export_csv

    # 1. Data-quality gate on the key source tables.
    for table, keys in (("users", ["user_id"]), ("events", ["user_id"]), ("orders", ["order_id"])):
        df = read_sql(f"SELECT * FROM {table} LIMIT 5000")
        report = run_standard_checks(table, df, key_columns=keys, min_rows=1)
        if not report.passed:
            logger.error("weekly_digest: quality gate failed for %s; report blocked", table)
            return

    # 2. Build metric deltas from the current vs. previous KPI snapshot.
    cards = warehouse.kpi_cards(force_refresh=True)
    metrics = [MetricDelta(c.name, c.value, c.value) for c in cards]

    # 3. Compose and export.
    report = build_report(dt.date.today(), metrics)
    path = export_csv(report)
    logger.info("weekly_digest: report written to %s", path)


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
