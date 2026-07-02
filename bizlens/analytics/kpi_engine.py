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


def active_users_sql(
    events_table: str = "events", user_col: str = "user_id",
    date_col: str = "event_date", window_days: int = 1,
) -> str:
    """Distinct active users over the trailing ``window_days`` (DAU/WAU/MAU)."""
    return f"""
    SELECT COUNT(DISTINCT {user_col}) AS active_users
    FROM {events_table}
    WHERE {date_col} >= CURRENT_DATE - INTERVAL '{window_days} days';
    """


def revenue_trend_sql(
    orders_table: str = "orders", date_col: str = "order_date",
    amount_col: str = "amount", days: int = 90,
) -> str:
    """Daily revenue for the trailing ``days`` — feeds the trend chart."""
    return f"""
    SELECT date_trunc('day', {date_col}) AS day,
           SUM({amount_col}) AS revenue
    FROM {orders_table}
    WHERE {date_col} >= CURRENT_DATE - INTERVAL '{days} days'
    GROUP BY 1 ORDER BY 1;
    """


def churn_rate_sql(
    users_table: str = "users", last_seen_col: str = "last_active_date",
    churn_window_days: int = 30,
) -> str:
    """Share of users with no activity in the last ``churn_window_days``."""
    return f"""
    SELECT
        COUNT(*) FILTER (
            WHERE {last_seen_col} < CURRENT_DATE - INTERVAL '{churn_window_days} days'
        )::float / NULLIF(COUNT(*), 0) AS churn_rate
    FROM {users_table};
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
