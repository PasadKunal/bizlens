"""FastAPI application: auth, KPI, cohort, funnel, ad-hoc query, and report routes.

Every analytics route reads through :mod:`bizlens.warehouse`, which runs under
the read-only analyst engine and caches the hot paths in Redis.
"""
from __future__ import annotations

import secrets

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from bizlens import __version__, warehouse
from bizlens.analytics import funnel_analysis
from bizlens.api.auth import create_access_token, current_user
from bizlens.config import get_settings
from bizlens.db import ping, sandboxed_query
from bizlens.sql.query_library import get_query, list_queries

app = FastAPI(
    title="BizLens API",
    version=__version__,
    description="Self-hosted BI: cohort, funnel, and KPI analytics with AI reporting.",
)


class FunnelRequest(BaseModel):
    steps: list[tuple[str, int]]


class LiveFunnelRequest(BaseModel):
    events: list[str] | None = None


class AdhocQueryRequest(BaseModel):
    sql: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__, "database": ping()}


@app.post("/auth/token")
def login(form: OAuth2PasswordRequestForm = Depends()) -> dict:
    """Issue a JWT for the built-in analyst account (dev user store)."""
    settings = get_settings()
    ok_user = secrets.compare_digest(form.username, settings.dev_username)
    ok_pass = secrets.compare_digest(form.password, settings.dev_password)
    if not (ok_user and ok_pass):
        raise HTTPException(401, "incorrect username or password")
    token = create_access_token(subject=form.username, pg_role=settings.analyst_role)
    return {"access_token": token, "token_type": "bearer"}


@app.get("/queries")
def queries() -> dict:
    """List the pre-built analytical queries available to the NL-to-SQL layer."""
    return {"queries": list_queries()}


@app.get("/kpi/cards")
def kpi_cards() -> dict:
    """Current KPI cards (DAU/WAU/MAU/revenue/churn), served from the Redis cache."""
    return {"cards": [c.__dict__ for c in warehouse.kpi_cards()]}


@app.get("/kpi/revenue-trend")
def revenue_trend(days: int = 90) -> dict:
    """Daily revenue series with anomaly flags."""
    return {"series": warehouse.revenue_trend(days=days).to_dict(orient="records")}


@app.get("/cohort/retention")
def cohort_retention(max_weeks: int = 12) -> dict:
    """Cohort-retention matrix (fractions) computed from the warehouse."""
    matrix = warehouse.retention_matrix(max_weeks=max_weeks)
    return {
        "cohorts": [str(i) for i in matrix.index],
        "weeks": [int(c) for c in matrix.columns],
        "matrix": matrix.round(4).values.tolist(),
    }


@app.post("/funnel/compute")
def funnel_compute(req: FunnelRequest) -> dict:
    """Compute funnel metrics from client-supplied step counts (stateless)."""
    steps = funnel_analysis.compute_funnel(req.steps)
    return {"steps": [s.__dict__ for s in steps]}


@app.post("/funnel/live")
def funnel_live(req: LiveFunnelRequest) -> dict:
    """Compute the funnel over live events for the given ordered event names."""
    steps = warehouse.funnel(req.events)
    return {"steps": [s.__dict__ for s in steps]}


@app.post("/query/adhoc")
def adhoc_query(req: AdhocQueryRequest, user: dict = Depends(current_user)) -> dict:
    """Execute a sandboxed SELECT under the caller's read-only role.

    SELECT-only, a server-side statement timeout, and a hard row cap are all
    enforced in :func:`bizlens.db.sandboxed_query`.
    """
    try:
        df = sandboxed_query(req.sql, role=user.get("pg_role"))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {
        "user": user["username"],
        "row_count": len(df),
        "columns": list(df.columns),
        "rows": df.to_dict(orient="records"),
    }


@app.get("/query/{name}")
def named_query(name: str) -> dict:
    try:
        return {"name": name, "sql": get_query(name)}
    except KeyError as exc:
        raise HTTPException(404, f"unknown query '{name}'") from exc
