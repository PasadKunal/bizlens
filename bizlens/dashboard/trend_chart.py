"""Trend chart with moving-average overlays and anomaly markers."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from bizlens.analytics.anomaly import scan_series
from bizlens.analytics.trend_analysis import moving_average


def trend_chart(
    series: pd.Series, title: str = "Metric Trend", windows: tuple[int, ...] = (7, 30)
) -> go.Figure:
    ma = moving_average(series, windows=windows)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(x=ma.index, y=ma["value"], mode="lines", name="value",
                   line={"color": "#94A3B8", "width": 1})
    )
    for w in windows:
        fig.add_trace(
            go.Scatter(x=ma.index, y=ma[f"ma_{w}"], mode="lines", name=f"{w}-day MA")
        )
    anomalies = scan_series(series.tolist())
    if anomalies:
        fig.add_trace(
            go.Scatter(
                x=series.index[anomalies], y=series.iloc[anomalies],
                mode="markers", name="anomaly",
                marker={"color": "#E11D48", "size": 10, "symbol": "x"},
            )
        )
    fig.update_layout(title=title, template="plotly_white")
    return fig
