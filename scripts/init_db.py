"""Initialise a fresh Postgres for BizLens: pgvector, read-only role, grants.

Used by CI (where the container's init SQL isn't mounted) and for a manual
bootstrap against any empty database. Idempotent. Connects as the application
role via ``DATABASE_URL``.
"""
from __future__ import annotations

from sqlalchemy import create_engine, text

from bizlens.config import get_settings

STATEMENTS = [
    "CREATE EXTENSION IF NOT EXISTS vector",
    "DO $$ BEGIN "
    "IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='bizlens_readonly') "
    "THEN CREATE ROLE bizlens_readonly LOGIN PASSWORD 'readonly'; END IF; END $$;",
    "GRANT USAGE ON SCHEMA public TO bizlens_readonly",
    "GRANT SELECT ON ALL TABLES IN SCHEMA public TO bizlens_readonly",
    "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO bizlens_readonly",
    "REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA public FROM bizlens_readonly",
]


def main() -> None:
    engine = create_engine(get_settings().database_url)
    with engine.begin() as conn:
        for stmt in STATEMENTS:
            conn.execute(text(stmt))
    print("database initialised (pgvector + read-only role + grants)")


if __name__ == "__main__":
    main()
