"""KPI card components for the Dash layout."""
from __future__ import annotations

from dash import html

from bizlens.analytics.kpi_engine import KPICard


def _format_value(card: KPICard) -> str:
    if card.unit == "ratio":
        return f"{card.value:.3f}"
    return f"{card.value:,.0f}"


def kpi_card(card: KPICard) -> html.Div:
    delta = ""
    color = "#64748B"
    if card.delta_pct is not None:
        arrow = "▲" if card.delta_pct >= 0 else "▼"
        color = "#16A34A" if card.delta_pct >= 0 else "#DC2626"
        delta = f"{arrow} {abs(card.delta_pct):.1f}%"
    border = "2px solid #E11D48" if card.is_anomaly else "1px solid #E2E8F0"
    return html.Div(
        [
            html.Div(card.name, style={"fontSize": "13px", "color": "#64748B"}),
            html.Div(_format_value(card), style={"fontSize": "28px", "fontWeight": 700}),
            html.Div(delta, style={"fontSize": "13px", "color": color}),
        ],
        style={
            "padding": "18px", "borderRadius": "10px", "border": border,
            "background": "white", "minWidth": "160px", "flex": "1",
        },
    )


def kpi_row(cards: list[KPICard]) -> html.Div:
    return html.Div(
        [kpi_card(c) for c in cards],
        style={"display": "flex", "gap": "16px", "flexWrap": "wrap"},
    )
