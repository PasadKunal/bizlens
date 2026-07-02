"""Funnel chart built from computed FunnelStep objects."""
from __future__ import annotations

import plotly.graph_objects as go

from bizlens.analytics.funnel_analysis import FunnelStep


def funnel_chart(steps: list[FunnelStep], title: str = "Conversion Funnel") -> go.Figure:
    fig = go.Figure(
        go.Funnel(
            y=[s.name for s in steps],
            x=[s.users for s in steps],
            textposition="inside",
            textinfo="value+percent initial",
            marker={"color": "#0F3460"},
        )
    )
    fig.update_layout(title=title, template="plotly_white")
    return fig
