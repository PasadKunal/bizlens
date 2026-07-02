"""Trend analysis: moving averages and period-over-period comparisons."""
from __future__ import annotations

import pandas as pd


def moving_average(series: pd.Series, windows: tuple[int, ...] = (7, 30, 90)) -> pd.DataFrame:
    """Return a DataFrame with the raw series plus one column per MA window."""
    out = pd.DataFrame({"value": series})
    for w in windows:
        out[f"ma_{w}"] = series.rolling(window=w, min_periods=1).mean()
    return out


def period_over_period(series: pd.Series, periods: int = 7) -> pd.Series:
    """Percentage change vs. ``periods`` ago (e.g. week-over-week for daily data)."""
    return series.pct_change(periods=periods) * 100.0


def rolling_zscore(series: pd.Series, window: int = 30) -> pd.Series:
    """Rolling z-score — a lightweight complement to the Welford detector for
    charting deviation bands on a dashboard."""
    mean = series.rolling(window=window, min_periods=2).mean()
    std = series.rolling(window=window, min_periods=2).std()
    return (series - mean) / std
