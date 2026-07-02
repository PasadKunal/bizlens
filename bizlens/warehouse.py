"""Data-access layer: executes the analytics SQL against the live warehouse and
caches the hot paths in Redis.

This is the single seam the API, dashboard, and scheduler all go through, so the
"compute KPIs / retention / funnel from Postgres" logic lives in exactly one
place. Everything here runs under the read-only analyst engine.
"""
from __future__ import annotations

import logging

import pandas as pd
from sqlalchemy import text

from bizlens.analytics import kpi_engine
from bizlens.analytics.anomaly import scan_series
from bizlens.analytics.cohort_analysis import retention_matrix_sql
from bizlens.analytics.funnel_analysis import FunnelStep, compute_funnel, funnel_sql
from bizlens.analytics.kpi_engine import KPICard
from bizlens.cache import get_json, set_json
from bizlens.db import get_analyst_engine, read_sql

logger = logging.getLogger(__name__)

KPI_CACHE_KEY = "kpi:cards"
REVENUE_CACHE_KEY = "kpi:revenue_trend"

# Default funnel for the seeded e-commerce dataset.
DEFAULT_FUNNEL = ["visit", "product_view", "add_to_cart", "checkout", "purchase"]


def data_now() -> str:
    """Return the latest event date in the warehouse as an ISO string.

    Used as the ``as_of`` anchor so trailing-window KPIs return rows even on a
    static seeded dataset. Falls back to ``CURRENT_DATE`` if there are no events.
    """
    df = read_sql("SELECT MAX(event_date)::date AS d FROM events")
    if df.empty or pd.isna(df.iloc[0]["d"]):
        return "CURRENT_DATE"
    return f"'{df.iloc[0]['d']}'"


def _scalar(sql: str) -> float:
    df = read_sql(sql)
    return float(df.iloc[0, 0]) if not df.empty and pd.notna(df.iloc[0, 0]) else 0.0


# --------------------------------------------------------------------------- #
# KPIs
# --------------------------------------------------------------------------- #
def compute_kpi_cards() -> list[KPICard]:
    """Compute the KPI card row directly from Postgres (no cache)."""
    as_of = data_now()
    dau = int(_scalar(kpi_engine.active_users_sql(window_days=1, as_of=as_of)))
    wau = int(_scalar(kpi_engine.active_users_sql(window_days=7, as_of=as_of)))
    mau = int(_scalar(kpi_engine.active_users_sql(window_days=30, as_of=as_of)))
    revenue = _scalar(kpi_engine.revenue_total_sql(days=30, as_of=as_of))
    churn = _scalar(kpi_engine.churn_rate_sql(churn_window_days=30, as_of=as_of))

    cards = kpi_engine.stack_active_user_cards(dau, wau, mau)
    cards.append(KPICard("Revenue (30d)", round(revenue, 2), "BRL", 30))
    cards.append(KPICard("Churn rate", round(churn, 4), "ratio", 30))
    return cards


def kpi_cards(force_refresh: bool = False) -> list[KPICard]:
    """Return KPI cards from Redis, recomputing on a miss or when forced."""
    if not force_refresh:
        cached = get_json(KPI_CACHE_KEY)
        if cached is not None:
            return [KPICard(**c) for c in cached]

    cards = compute_kpi_cards()
    set_json(KPI_CACHE_KEY, [c.__dict__ for c in cards])
    return cards


def revenue_trend(days: int = 90, force_refresh: bool = False) -> pd.DataFrame:
    """Daily revenue series with anomaly flags, cached in Redis."""
    if not force_refresh:
        cached = get_json(REVENUE_CACHE_KEY)
        if cached is not None:
            return pd.DataFrame(cached)

    as_of = data_now()
    df = read_sql(kpi_engine.revenue_trend_sql(days=days, as_of=as_of))
    if not df.empty:
        anomalies = set(scan_series(df["revenue"].astype(float).tolist()))
        df["is_anomaly"] = [i in anomalies for i in range(len(df))]
    set_json(REVENUE_CACHE_KEY, df.to_dict(orient="records"))
    return df


# --------------------------------------------------------------------------- #
# Cohort retention
# --------------------------------------------------------------------------- #
def retention_matrix(max_weeks: int = 12) -> pd.DataFrame:
    """Fetch the cohort-retention grid (fractions) from Postgres.

    Runs the single window-function query, joins in each cohort's size, and
    pivots to a ``cohort_week x week_offset`` matrix of retention fractions.
    """
    long = read_sql(retention_matrix_sql(max_weeks=max_weeks))
    if long.empty:
        return pd.DataFrame()

    sizes = read_sql(
        "SELECT date_trunc('week', signup_date) AS cohort_week, "
        "COUNT(*) AS cohort_size FROM users GROUP BY 1"
    ).set_index("cohort_week")["cohort_size"]

    grid = long.pivot(index="cohort_week", columns="week_offset", values="active_users").fillna(0)
    matrix = grid.div(sizes, axis=0)
    return matrix.sort_index()


# --------------------------------------------------------------------------- #
# Funnel
# --------------------------------------------------------------------------- #
def funnel(step_events: list[str] | None = None) -> list[FunnelStep]:
    """Compute the conversion funnel over the given ordered events."""
    step_events = step_events or DEFAULT_FUNNEL
    row = read_sql(funnel_sql("events", step_events))
    counts = [(ev, int(row.iloc[0][ev])) for ev in step_events]
    return compute_funnel(counts)


# --------------------------------------------------------------------------- #
# Ad-hoc
# --------------------------------------------------------------------------- #
def explain_available() -> bool:
    """Cheap connectivity probe used by health checks."""
    try:
        with get_analyst_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
