"""pgvector-backed store for the NL-to-SQL query templates.

Each pre-built query in the library is embedded and stored with its embedding
in a ``query_embeddings`` table. A natural-language question is embedded the
same way and matched by cosine distance (pgvector's ``<=>`` operator).

Run ``python -m bizlens.sql.vector_store`` after the ETL to (re)build the index.
"""
from __future__ import annotations

import logging

from sqlalchemy import Engine, text

from bizlens.db import get_analyst_engine, get_engine
from bizlens.nlp.embeddings import active_backend, embed, embedding_dim, to_pgvector
from bizlens.sql.query_library import QUERY_LIBRARY

logger = logging.getLogger(__name__)

TABLE = "query_embeddings"


def build(engine: Engine | None = None) -> int:
    """(Re)create the embedding table and index every query-library template.

    Idempotent: drops and recreates the table so a change of embedding backend
    (and thus dimension) is handled cleanly. Returns the number of templates
    indexed.
    """
    engine = engine or get_engine()
    dim = embedding_dim()

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text(f"DROP TABLE IF EXISTS {TABLE}"))
        conn.execute(
            text(
                f"CREATE TABLE {TABLE} ("
                "  name text PRIMARY KEY,"
                "  description text NOT NULL,"
                "  sql text NOT NULL,"
                f"  embedding vector({dim}) NOT NULL"
                ")"
            )
        )
        for name, meta in QUERY_LIBRARY.items():
            vec = to_pgvector(embed(meta["description"] + " " + name.replace("_", " ")))
            conn.execute(
                text(
                    f"INSERT INTO {TABLE} (name, description, sql, embedding) "
                    f"VALUES (:n, :d, :s, '{vec}'::vector)"
                ),
                {"n": name, "d": meta["description"], "s": meta["sql"].strip()},
            )
        # HNSW index for cosine distance (overkill at this corpus size, but this
        # is how it scales - and it exercises the real pgvector index path).
        conn.execute(
            text(
                f"CREATE INDEX ON {TABLE} USING hnsw (embedding vector_cosine_ops)"
            )
        )

    logger.info("indexed %d query templates (%s backend, dim=%d)",
                len(QUERY_LIBRARY), active_backend(), dim)
    return len(QUERY_LIBRARY)


def search(question: str, k: int = 1, engine: Engine | None = None) -> list[dict]:
    """Return the ``k`` closest query templates to ``question`` by cosine distance."""
    engine = engine or get_analyst_engine()
    vec = to_pgvector(embed(question))
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                f"SELECT name, description, sql, "
                f"       1 - (embedding <=> '{vec}'::vector) AS similarity "
                f"FROM {TABLE} ORDER BY embedding <=> '{vec}'::vector LIMIT :k"
            ),
            {"k": k},
        ).mappings().all()
    return [dict(r) for r in rows]


def is_built(engine: Engine | None = None) -> bool:
    """True if the embedding table exists and is populated."""
    engine = engine or get_analyst_engine()
    try:
        with engine.connect() as conn:
            n = conn.execute(text(f"SELECT COUNT(*) FROM {TABLE}")).scalar()
        return bool(n)
    except Exception:
        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    build()
