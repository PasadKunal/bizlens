"""Database connection helpers.

Two engines are exposed:

* :func:`get_engine`          — the application role (read/write, used by ETL).
* :func:`get_analyst_engine`  — the SELECT-only analyst role used by every
  analytics query. Running analytics through the read-only role is the core
  safety guarantee of the platform: no analytical query can mutate data.
"""
from __future__ import annotations

from functools import lru_cache

import pandas as pd
from sqlalchemy import Engine, create_engine, text

from bizlens.config import get_settings


@lru_cache
def get_engine() -> Engine:
    """Read/write engine for the application role (ETL, migrations)."""
    return create_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def get_analyst_engine() -> Engine:
    """SELECT-only engine used by all analytics queries."""
    return create_engine(get_settings().analyst_database_url, pool_pre_ping=True)


def read_sql(sql: str, engine: Engine | None = None, params: dict | None = None) -> pd.DataFrame:
    """Execute ``sql`` against the analyst engine and return a DataFrame."""
    engine = engine or get_analyst_engine()
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})


def ping(engine: Engine | None = None) -> bool:
    """Return True if the database is reachable."""
    engine = engine or get_analyst_engine()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def sandboxed_query(
    sql: str,
    role: str | None = None,
    scope: str | None = None,
    timeout_seconds: int | None = None,
    row_cap: int | None = None,
) -> pd.DataFrame:
    """Run a read-only SELECT under the analyst role with hard safety limits.

    * ``statement_timeout`` aborts runaway queries server-side.
    * the query is wrapped in ``SELECT * FROM (...) LIMIT cap`` so an enormous
      result set can never be materialised, even if the caller omits a LIMIT.
    * ``scope`` sets the ``bizlens.scope`` session variable that the row-level
      security policies filter on, so a scoped user only sees permitted rows.

    Only ``SELECT`` statements are accepted; anything else raises ``ValueError``.
    """
    settings = get_settings()
    timeout_seconds = timeout_seconds or settings.adhoc_query_timeout_seconds
    row_cap = row_cap or settings.adhoc_query_row_cap

    cleaned = sql.strip().rstrip(";")
    if not cleaned.lower().startswith("select"):
        raise ValueError("only SELECT statements are permitted")

    wrapped = f"SELECT * FROM (\n{cleaned}\n) AS _bizlens_sandbox LIMIT {row_cap}"
    engine = get_analyst_engine()
    with engine.connect() as conn:
        conn.execute(text(f"SET statement_timeout = {timeout_seconds * 1000}"))
        if scope:
            # set_config passes the value as a bound parameter (no injection).
            conn.execute(
                text("SELECT set_config('bizlens.scope', :scope, false)"),
                {"scope": scope},
            )
        return pd.read_sql(text(wrapped), conn)
