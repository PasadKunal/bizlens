"""Retention-matrix heatmap (Amplitude-style) built with Plotly."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go


def retention_heatmap(matrix: pd.DataFrame) -> go.Figure:
    """Render a cohort x week-offset retention matrix as a heatmap.

    ``matrix`` rows are cohorts, columns are week offsets, values are retention
    fractions (0..1).
    """
    z = (matrix * 100).round(1)
    fig = go.Figure(
        data=go.Heatmap(
            z=z.values,
            x=[f"W{c}" for c in matrix.columns],
            y=[str(i.date()) if hasattr(i, "date") else str(i) for i in matrix.index],
            colorscale="Blues",
            texttemplate="%{z}%",
            hovertemplate="Cohort %{y}<br>%{x}: %{z}%<extra></extra>",
            colorbar={"title": "Retention %"},
        )
    )
    fig.update_layout(
        title="Weekly Cohort Retention",
        xaxis_title="Weeks since signup",
        yaxis_title="Signup cohort",
        template="plotly_white",
    )
    return fig
