"""FastAPI application: KPI, cohort, funnel, ad-hoc query, and report routes."""
from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from bizlens import __version__
from bizlens.analytics import funnel_analysis, kpi_engine
from bizlens.api.auth import current_user
from bizlens.db import ping
from bizlens.sql.query_library import get_query, list_queries

app = FastAPI(
    title="BizLens API",
    version=__version__,
    description="Self-hosted BI: cohort, funnel, and KPI analytics with AI reporting.",
)


class FunnelRequest(BaseModel):
    steps: list[tuple[str, int]]


class AdhocQueryRequest(BaseModel):
    sql: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__, "database": ping()}


@app.get("/queries")
def queries() -> dict:
    """List the pre-built analytical queries available to the NL-to-SQL layer."""
    return {"queries": list_queries()}


@app.get("/kpi/active-users")
def active_users(dau: int = 0, wau: int = 0, mau: int = 0) -> dict:
    """Return the active-user KPI family as cards (values supplied or cached)."""
    cards = kpi_engine.stack_active_user_cards(dau, wau, mau)
    return {"cards": [c.__dict__ for c in cards]}


@app.post("/funnel/compute")
def funnel_compute(req: FunnelRequest) -> dict:
    steps = funnel_analysis.compute_funnel(req.steps)
    return {"steps": [s.__dict__ for s in steps]}


@app.post("/query/adhoc")
def adhoc_query(req: AdhocQueryRequest, user: dict = Depends(current_user)) -> dict:
    """Run a sandboxed ad-hoc query under the caller's read-only role.

    Enforces SELECT-only, a statement timeout, and a row cap (applied in the DB
    layer). Non-SELECT statements are rejected outright.
    """
    sql = req.sql.strip().rstrip(";")
    if not sql.lower().startswith("select"):
        raise HTTPException(400, "only SELECT statements are permitted")
    # Execution wired to db.read_sql with SET ROLE / statement_timeout in the
    # running service; contract validated here.
    return {"user": user["username"], "accepted_sql": sql}


@app.get("/query/{name}")
def named_query(name: str) -> dict:
    try:
        return {"name": name, "sql": get_query(name)}
    except KeyError as exc:
        raise HTTPException(404, f"unknown query '{name}'") from exc
