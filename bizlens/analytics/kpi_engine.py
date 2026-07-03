"""KPI computation engine: DAU/MAU/WAU, revenue, conversion, churn.

Each KPI is expressed as SQL against the analyst (read-only) role. The results
are small scalars/series that the dashboard reads from Redis (pre-aggregated on
a schedule) rather than recomputing on every page load.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class KPICard:
    name: str
    value: float
    unit: str
    lookback_days: int
    delta_pct: float | None = None
    is_anomaly: bool = False


# ``as_of`` is the reference "now" for trailing windows. It defaults to the
# database's CURRENT_DATE for live use; when running against a seeded dataset the
# warehouse layer passes the latest data date so windows still return rows.


def active_users_sql(
    events_table: str = "events", user_col: str = "user_id",
    date_col: str = "event_date", window_days: int = 1, as_of: str = "CURRENT_DATE",
) -> str:
    """Distinct active users over the trailing ``window_days`` (DAU/WAU/MAU)."""
    return f"""
    SELECT COUNT(DISTINCT {user_col}) AS active_users
    FROM {events_table}
    WHERE {date_col} > ({as_of})::date - INTERVAL '{window_days} days';
    """


def revenue_trend_sql(
    orders_table: str = "orders", date_col: str = "order_date",
    amount_col: str = "amount", days: int = 90, as_of: str = "CURRENT_DATE",
) -> str:
    """Daily revenue for the trailing ``days`` - feeds the trend chart."""
    return f"""
    SELECT date_trunc('day', {date_col})::date AS day,
           SUM({amount_col}) AS revenue
    FROM {orders_table}
    WHERE {date_col} > ({as_of})::date - INTERVAL '{days} days'
    GROUP BY 1 ORDER BY 1;
    """


def revenue_total_sql(
    orders_table: str = "orders", date_col: str = "order_date",
    amount_col: str = "amount", days: int = 30, as_of: str = "CURRENT_DATE",
) -> str:
    """Total revenue over the trailing ``days`` - feeds a KPI card."""
    return f"""
    SELECT COALESCE(SUM({amount_col}), 0) AS revenue
    FROM {orders_table}
    WHERE {date_col} > ({as_of})::date - INTERVAL '{days} days';
    """


def churn_rate_sql(
    events_table: str = "events", user_col: str = "user_id",
    date_col: str = "event_date", churn_window_days: int = 30,
    as_of: str = "CURRENT_DATE",
) -> str:
    """Share of users whose most recent activity is older than the churn window.

    Last-activity is derived from the events table (no dependency on a
    denormalised ``last_active_date`` column).
    """
    return f"""
    WITH last_seen AS (
        SELECT {user_col} AS user_id, MAX({date_col}) AS last_active
        FROM {events_table}
        GROUP BY {user_col}
    )
    SELECT
        COUNT(*) FILTER (
            WHERE last_active < ({as_of})::date - INTERVAL '{churn_window_days} days'
        )::float / NULLIF(COUNT(*), 0) AS churn_rate
    FROM last_seen;
    """


def stack_active_user_cards(dau: int, wau: int, mau: int) -> list[KPICard]:
    """Package the active-user family into cards, including stickiness (DAU/MAU)."""
    cards = [
        KPICard("DAU", dau, "users", 1),
        KPICard("WAU", wau, "users", 7),
        KPICard("MAU", mau, "users", 30),
    ]
    if mau:
        cards.append(KPICard("Stickiness (DAU/MAU)", round(dau / mau, 3), "ratio", 30))
    return cards


def compute_delta(current: float, previous: float) -> float | None:
    """Percentage change vs. the previous period (None if previous is 0)."""
    if not previous:
        return None
    return round((current - previous) / previous * 100.0, 2)


def series_to_cards(df: pd.DataFrame, value_col: str, name: str, unit: str) -> KPICard:
    """Build a single card from the last value of a trend DataFrame."""
    if df.empty:
        return KPICard(name, 0.0, unit, len(df))
    current = float(df[value_col].iloc[-1])
    previous = float(df[value_col].iloc[-2]) if len(df) > 1 else 0.0
    return KPICard(name, current, unit, len(df), delta_pct=compute_delta(current, previous))
