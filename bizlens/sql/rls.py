"""Row-level security policies for per-user data scoping.

Each analytics table carries a ``country`` column (denormalised in the ETL).
A policy scopes visible rows to a session variable, ``bizlens.scope``:

* unset / ``NULL``  -> see everything (admin / internal jobs / dashboard)
* ``'ALL'``         -> see everything
* a country code    -> see only that country's rows

The API sets ``bizlens.scope`` from the caller's JWT, so a scoped user cannot
read another scope's rows even with a hand-crafted ``WHERE`` clause - the filter
is enforced by Postgres, not the application. Policies apply to the non-owner
read-only role; the ``bizlens`` owner (used by the ETL) bypasses them.
"""
from __future__ import annotations

import logging

from sqlalchemy import Engine, text

from bizlens.db import get_engine

logger = logging.getLogger(__name__)

RLS_TABLES = ("users", "events", "orders")
POLICY = "scope_isolation"


def apply_rls(engine: Engine | None = None, tables: tuple[str, ...] = RLS_TABLES) -> None:
    """Enable RLS and (re)create the scope policy on each table.

    Idempotent - safe to run after every ETL (which drops/recreates tables and
    therefore their policies).
    """
    engine = engine or get_engine()
    with engine.begin() as conn:
        for t in tables:
            conn.execute(text(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY"))
            conn.execute(text(f"DROP POLICY IF EXISTS {POLICY} ON {t}"))
            conn.execute(
                text(
                    f"CREATE POLICY {POLICY} ON {t} FOR SELECT USING ("
                    "  current_setting('bizlens.scope', true) IS NULL"
                    "  OR current_setting('bizlens.scope', true) = 'ALL'"
                    "  OR country = current_setting('bizlens.scope', true)"
                    ")"
                )
            )
    logger.info("applied RLS scope policy to %s", ", ".join(tables))
