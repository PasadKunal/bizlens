"""Funnel analysis: step drop-off, A/B comparison, time-to-convert."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from bizlens.analytics.statistical_tests import ProportionTestResult, two_proportion_chi_square


@dataclass
class FunnelStep:
    name: str
    users: int
    conversion_from_start: float
    conversion_from_prev: float
    dropoff_from_prev: float


def compute_funnel(step_counts: list[tuple[str, int]]) -> list[FunnelStep]:
    """Compute per-step conversion and drop-off.

    Parameters
    ----------
    step_counts : ordered ``(step_name, user_count)`` pairs, monotonically
        non-increasing (each step is a subset of the previous one).
    """
    if not step_counts:
        return []
    start = step_counts[0][1]
    steps: list[FunnelStep] = []
    prev = start
    for name, count in step_counts:
        conv_start = count / start if start else 0.0
        conv_prev = count / prev if prev else 0.0
        steps.append(
            FunnelStep(
                name=name,
                users=count,
                conversion_from_start=conv_start,
                conversion_from_prev=conv_prev,
                dropoff_from_prev=1.0 - conv_prev,
            )
        )
        prev = count
    return steps


def compare_funnels(
    seg_a: list[tuple[str, int]], seg_b: list[tuple[str, int]], alpha: float = 0.05
) -> dict[str, ProportionTestResult]:
    """Compare overall step-to-step conversion between two segments.

    Returns, per step (after the first), a chi-squared test of that step's
    conversion-from-previous between segment A and B.
    """
    results: dict[str, ProportionTestResult] = {}
    for i in range(1, min(len(seg_a), len(seg_b))):
        name = seg_a[i][0]
        results[name] = two_proportion_chi_square(
            conv_a=seg_a[i][1], n_a=seg_a[i - 1][1],
            conv_b=seg_b[i][1], n_b=seg_b[i - 1][1],
            alpha=alpha,
        )
    return results


def time_to_convert_distribution(
    timestamps: pd.DataFrame, user_col: str = "user_id",
    step_col: str = "step", ts_col: str = "ts",
    from_step: str | None = None, to_step: str | None = None,
) -> pd.Series:
    """Time (in hours) each user took to move between two funnel steps."""
    df = timestamps.sort_values(ts_col)
    pivot = df.pivot_table(index=user_col, columns=step_col, values=ts_col, aggfunc="min")
    steps = list(pivot.columns)
    a = from_step or steps[0]
    b = to_step or steps[-1]
    delta = (pd.to_datetime(pivot[b]) - pd.to_datetime(pivot[a])).dt.total_seconds() / 3600.0
    return delta.dropna()


def funnel_sql(
    events_table: str, step_events: list[str],
    user_col: str = "user_id", event_col: str = "event_name",
) -> str:
    """Build SQL counting distinct users reaching each ordered funnel step."""
    ctes = []
    for i, ev in enumerate(step_events):
        ctes.append(
            f"step_{i} AS (SELECT DISTINCT {user_col} FROM {events_table} "
            f"WHERE {event_col} = '{ev}')"
        )
    selects = ", ".join(
        f"(SELECT COUNT(*) FROM step_{i}) AS \"{ev}\""
        for i, ev in enumerate(step_events)
    )
    return "WITH " + ",\n".join(ctes) + f"\nSELECT {selects};"
