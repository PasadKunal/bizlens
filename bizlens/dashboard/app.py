"""BizLens dashboard entry point (Plotly Dash).

Run locally with::

    python -m bizlens.dashboard.app

The dashboard renders from the live warehouse when it is reachable, and falls
back to bundled demo data otherwise so the UI is always explorable.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from dash import Dash, Input, Output, dcc, html

from bizlens import warehouse
from bizlens.analytics.funnel_analysis import FunnelStep, compute_funnel
from bizlens.analytics.kpi_engine import KPICard
from bizlens.dashboard.funnel_chart import funnel_chart
from bizlens.dashboard.kpi_cards import kpi_row
from bizlens.dashboard.nl_to_sql import resolve as resolve_nl
from bizlens.dashboard.retention_heatmap import retention_heatmap
from bizlens.dashboard.trend_chart import trend_chart

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Demo fallbacks (used only when the warehouse is unreachable)
# --------------------------------------------------------------------------- #
def _demo_retention() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    weeks = range(12)
    cohorts = pd.date_range("2024-01-01", periods=12, freq="W")
    data = {w: [max(0.0, 1.0 * (0.72**w) + rng.normal(0, 0.02)) for _ in cohorts] for w in weeks}
    df = pd.DataFrame(data, index=cohorts)
    df[0] = 1.0
    return df


def _demo_trend() -> pd.Series:
    rng = np.random.default_rng(7)
    idx = pd.date_range("2024-01-01", periods=90, freq="D")
    base = 1000 + np.cumsum(rng.normal(5, 40, size=90))
    base[60] *= 1.8  # injected anomaly
    return pd.Series(base, index=idx)


def _demo_cards() -> list[KPICard]:
    return [
        KPICard("DAU", 4820, "users", 1, delta_pct=3.2),
        KPICard("MAU", 41230, "users", 30, delta_pct=1.1),
        KPICard("Revenue (30d)", 284500, "BRL", 30, delta_pct=-4.7, is_anomaly=True),
        KPICard("Churn rate", 0.062, "ratio", 30, delta_pct=-0.8),
    ]


def _demo_funnel() -> list[FunnelStep]:
    return compute_funnel(
        [("Visit", 10000), ("Product view", 6200), ("Add to cart", 2800),
         ("Checkout", 1500), ("Purchase", 980)]
    )


# --------------------------------------------------------------------------- #
# Live loaders with fallback
# --------------------------------------------------------------------------- #
def load_cards() -> tuple[list[KPICard], bool]:
    try:
        return warehouse.kpi_cards(), True
    except Exception as exc:  # noqa: BLE001 - any failure -> demo mode
        logger.warning("KPI cards unavailable, using demo data: %s", exc)
        return _demo_cards(), False


def load_trend() -> pd.Series:
    try:
        df = warehouse.revenue_trend()
        if not df.empty:
            return pd.Series(df["revenue"].astype(float).values, index=pd.to_datetime(df["day"]))
    except Exception as exc:  # noqa: BLE001
        logger.warning("revenue trend unavailable, using demo data: %s", exc)
    return _demo_trend()


def load_retention() -> pd.DataFrame:
    try:
        m = warehouse.retention_matrix()
        if not m.empty:
            return m
    except Exception as exc:  # noqa: BLE001
        logger.warning("retention matrix unavailable, using demo data: %s", exc)
    return _demo_retention()


def load_funnel() -> list[FunnelStep]:
    try:
        steps = warehouse.funnel()
        if steps and steps[0].users > 0:
            return steps
    except Exception as exc:  # noqa: BLE001
        logger.warning("funnel unavailable, using demo data: %s", exc)
    return _demo_funnel()


def build_app() -> Dash:
    app = Dash(__name__, title="BizLens")

    cards, live = load_cards()
    source = "live warehouse" if live else "demo data (warehouse unreachable)"

    app.layout = html.Div(
        style={"maxWidth": "1100px", "margin": "0 auto", "padding": "24px",
               "fontFamily": "Inter, system-ui, sans-serif"},
        children=[
            html.H1("BizLens", style={"marginBottom": "4px"}),
            html.P("Self-hosted business intelligence — cohorts, funnels, KPIs.",
                   style={"color": "#64748B", "marginTop": 0}),
            html.Div(f"Data source: {source}",
                     style={"fontSize": "12px", "color": "#94A3B8", "marginBottom": "12px"}),
            html.H3("Key metrics"),
            kpi_row(cards),
            html.H3("Revenue trend", style={"marginTop": "28px"}),
            dcc.Graph(figure=trend_chart(load_trend(), title="Daily Revenue (90d)")),
            html.H3("Cohort retention"),
            dcc.Graph(figure=retention_heatmap(load_retention())),
            html.H3("Conversion funnel"),
            dcc.Graph(figure=funnel_chart(load_funnel())),
            html.Div(id="nl-section", children=[
                html.H3("Ask a question (NL → SQL)"),
                dcc.Input(id="nl-input", type="text",
                          placeholder="e.g. weekly active users by country",
                          style={"width": "100%", "padding": "10px"}),
                html.Pre(id="nl-output", style={"background": "#0F172A", "color": "#E2E8F0",
                                                "padding": "16px", "borderRadius": "8px",
                                                "whiteSpace": "pre-wrap"}),
            ]),
        ],
    )

    @app.callback(Output("nl-output", "children"), Input("nl-input", "value"))
    def _resolve(question: str | None) -> str:
        if not question:
            return "Type a question to get a validated SQL query."
        match = resolve_nl(question)
        if not match:
            return "No matching query template found."
        return (f"-- {match.description}\n"
                f"-- matched via {match.backend} (score {match.score:.2f})\n{match.sql}")

    return app


app = build_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050)
