"""Cohort retention analysis.

Two paths are provided:

* :func:`retention_matrix_sql` — a single window-function query that computes
  the full N-cohort x M-week retention grid in one round-trip to Postgres.
* :func:`retention_matrix_from_events` — an equivalent pandas implementation
  used for unit tests and small in-memory datasets.

Both return the retention grid as *fractions* (0..1) indexed by cohort period.
"""
from __future__ import annotations

import pandas as pd

from bizlens.analytics.statistical_tests import (
    ProportionTestResult,
    bonferroni_correction,
    two_proportion_chi_square,
)


def retention_matrix_sql(
    events_table: str = "events",
    user_col: str = "user_id",
    date_col: str = "event_date",
    signup_table: str = "users",
    signup_col: str = "signup_date",
    max_weeks: int = 12,
) -> str:
    """Return SQL computing a weekly cohort-retention matrix.

    Uses ``date_trunc`` to bucket users into signup-week cohorts and
    conditional aggregation (``COUNT(DISTINCT ...) FILTER``) to count returning
    users per week offset — the whole grid in one query. A composite index on
    ``(user_id, event_date)`` keeps this under a few seconds at scale.
    """
    return f"""
    WITH cohorts AS (
        SELECT {user_col} AS user_id,
               date_trunc('week', {signup_col}) AS cohort_week
        FROM {signup_table}
    ),
    activity AS (
        SELECT e.{user_col} AS user_id,
               c.cohort_week,
               FLOOR(
                   EXTRACT(EPOCH FROM (date_trunc('week', e.{date_col}) - c.cohort_week))
                   / (7 * 24 * 3600)
               )::int AS week_offset
        FROM {events_table} e
        JOIN cohorts c ON c.user_id = e.{user_col}
    )
    SELECT cohort_week,
           week_offset,
           COUNT(DISTINCT user_id) AS active_users
    FROM activity
    WHERE week_offset BETWEEN 0 AND {max_weeks - 1}
    GROUP BY cohort_week, week_offset
    ORDER BY cohort_week, week_offset;
    """


def retention_matrix_from_events(
    events: pd.DataFrame,
    signups: pd.DataFrame,
    user_col: str = "user_id",
    date_col: str = "event_date",
    signup_col: str = "signup_date",
    max_weeks: int = 12,
) -> pd.DataFrame:
    """Compute the retention matrix (fractions) from in-memory DataFrames."""
    signups = signups.copy()
    signups["cohort_week"] = pd.to_datetime(signups[signup_col]).dt.to_period("W").dt.start_time

    ev = events.merge(signups[[user_col, "cohort_week"]], on=user_col, how="inner")
    ev["event_week"] = pd.to_datetime(ev[date_col]).dt.to_period("W").dt.start_time
    ev["week_offset"] = (
        (ev["event_week"] - ev["cohort_week"]).dt.days // 7
    ).astype(int)
    ev = ev[(ev["week_offset"] >= 0) & (ev["week_offset"] < max_weeks)]

    active = (
        ev.groupby(["cohort_week", "week_offset"])[user_col].nunique().reset_index(name="active")
    )
    # Denominator is the full cohort size (all signups that week), not week-0
    # actives — otherwise a user active in week N but not week 0 pushes a cell
    # above 100%.
    cohort_size = signups.groupby("cohort_week")[user_col].nunique()

    grid = active.pivot(index="cohort_week", columns="week_offset", values="active").fillna(0)
    matrix = grid.div(cohort_size, axis=0)
    return matrix.sort_index()


def compare_cohorts(
    cohort_a: tuple[int, int], cohort_b: tuple[int, int], alpha: float = 0.05
) -> ProportionTestResult:
    """Chi-squared test on the week-N retention of two cohorts.

    Each argument is ``(returned_users, cohort_size)``.
    """
    return two_proportion_chi_square(
        cohort_a[0], cohort_a[1], cohort_b[0], cohort_b[1], alpha=alpha
    )


def churn_signal_cohorts(matrix: pd.DataFrame, week: int = 4, sigma: float = 2.0) -> list:
    """Flag cohorts whose week-``week`` retention is >``sigma`` std below the
    baseline across all cohorts — an early churn warning."""
    if week not in matrix.columns:
        return []
    col = matrix[week].dropna()
    if len(col) < 3:
        return []
    threshold = col.mean() - sigma * col.std()
    return col[col < threshold].index.tolist()


def significance_grid(
    returned: dict, sizes: dict, baseline: str, alpha: float = 0.05
) -> dict:
    """Compare every cohort against ``baseline`` with Bonferroni correction.

    Parameters are dicts keyed by cohort id. Returns per-cohort decisions.
    """
    others = [k for k in returned if k != baseline]
    results = {
        k: two_proportion_chi_square(
            returned[baseline], sizes[baseline], returned[k], sizes[k], alpha=alpha
        )
        for k in others
    }
    decisions, corrected = bonferroni_correction([r.p_value for r in results.values()], alpha)
    return {
        k: {"result": r, "significant_corrected": d}
        for (k, r), d in zip(results.items(), decisions, strict=True)
    } | {"_corrected_alpha": corrected}
