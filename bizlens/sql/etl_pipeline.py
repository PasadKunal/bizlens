"""ETL: load the seed dataset (Brazilian Olist) from CSV into PostgreSQL.

The pipeline is deliberately simple and idempotent: read CSV -> normalise ->
validate schema -> load. Run it once after ``docker-compose up`` to seed the
warehouse. See ``scripts/generate_sample_data.py`` for a synthetic fallback
when the Kaggle dataset is not present.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
from sqlalchemy import Engine

from bizlens.db import get_engine
from bizlens.sql.schema_validator import validate_schema

logger = logging.getLogger(__name__)

# Map of table name -> CSV filename under data/processed.
TABLES = ("users", "events", "orders")


def load_csv(table: str, data_dir: Path) -> pd.DataFrame:
    """Load and lightly normalise a single table's CSV."""
    path = data_dir / f"{table}.csv"
    df = pd.read_csv(path)
    for col in df.columns:
        if col.endswith("_date"):
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def load_table(table: str, df: pd.DataFrame, engine: Engine, if_exists: str = "replace") -> int:
    """Validate schema then write ``df`` to Postgres. Returns rows written."""
    report = validate_schema(table, df)
    if not report.ok:
        raise ValueError(
            f"schema validation failed for '{table}': "
            f"missing={report.missing_columns} mismatches={report.type_mismatches}"
        )
    df.to_sql(table, engine, if_exists=if_exists, index=False, chunksize=5000)
    logger.info("loaded %d rows into %s", len(df), table)
    return len(df)


def run(data_dir: str | Path = "data/processed", engine: Engine | None = None) -> dict[str, int]:
    """Run the full ETL for all known tables. Returns per-table row counts."""
    data_dir = Path(data_dir)
    engine = engine or get_engine()
    counts: dict[str, int] = {}
    for table in TABLES:
        df = load_csv(table, data_dir)
        counts[table] = load_table(table, df, engine)
    return counts


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(run())
