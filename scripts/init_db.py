"""Initialise a fresh Postgres for BizLens: pgvector, read-only role, grants.

Used by CI (where the container's init SQL isn't mounted) and for a manual
bootstrap against any empty database. Idempotent. Connects as the application
role via ``DATABASE_URL``.

The read-only role name and password come from the environment so a managed
host that enforces password strength (e.g. Neon) can use a strong one:

    ANALYST_ROLE         (default: bizlens_readonly)
    ANALYST_DB_PASSWORD  (default: readonly)

Whatever password is set here must match the one embedded in
ANALYST_DATABASE_URL.
"""
from __future__ import annotations

import os

from sqlalchemy import create_engine, text

from bizlens.config import get_settings


def statements() -> list[str]:
    role = os.environ.get("ANALYST_ROLE", "bizlens_readonly")
    password = os.environ.get("ANALYST_DB_PASSWORD", "readonly")
    return [
        "CREATE EXTENSION IF NOT EXISTS vector",
        f"DO $$ BEGIN "
        f"IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='{role}') "
        f"THEN CREATE ROLE {role} LOGIN PASSWORD '{password}'; END IF; END $$;",
        f"GRANT USAGE ON SCHEMA public TO {role}",
        f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {role}",
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO {role}",
        f"REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA public FROM {role}",
    ]


def main() -> None:
    engine = create_engine(get_settings().database_url)
    with engine.begin() as conn:
        for stmt in statements():
            conn.execute(text(stmt))
    print("database initialised (pgvector + read-only role + grants)")


if __name__ == "__main__":
    main()
