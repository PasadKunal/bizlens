"""Query optimization helper.

Runs ``EXPLAIN (ANALYZE, FORMAT JSON)`` on a query, walks the plan for
sequential scans on large tables, and suggests composite index candidates.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from sqlalchemy import Engine, text

from bizlens.db import get_analyst_engine


@dataclass
class IndexSuggestion:
    table: str
    columns: list[str]
    reason: str

    @property
    def ddl(self) -> str:
        cols = ", ".join(self.columns)
        return f"CREATE INDEX idx_{self.table}_{'_'.join(self.columns)} ON {self.table} ({cols});"


def explain(sql: str, engine: Engine | None = None) -> dict:
    """Return the JSON EXPLAIN ANALYZE plan for ``sql``."""
    engine = engine or get_analyst_engine()
    with engine.connect() as conn:
        row = conn.execute(text(f"EXPLAIN (ANALYZE, FORMAT JSON) {sql}")).scalar()
    return row[0] if isinstance(row, list) else json.loads(row)[0]


def _walk(node: dict, seq_scans: list[dict]) -> None:
    if node.get("Node Type") == "Seq Scan":
        seq_scans.append(node)
    for child in node.get("Plans", []):
        _walk(child, seq_scans)


def suggest_indexes(plan: dict, row_threshold: int = 10_000) -> list[IndexSuggestion]:
    """Suggest indexes for sequential scans over large tables.

    Filter/`Cond` columns on a seq-scanned table are the natural composite-index
    candidates.
    """
    seq_scans: list[dict] = []
    _walk(plan.get("Plan", plan), seq_scans)

    suggestions: list[IndexSuggestion] = []
    for scan in seq_scans:
        rows = scan.get("Plan Rows", 0)
        if rows < row_threshold:
            continue
        table = scan.get("Relation Name", "unknown")
        cond = scan.get("Filter", "") or scan.get("Recheck Cond", "")
        cols = sorted(set(re.findall(r"\b([a-z_][a-z0-9_]*)\s*[=<>]", cond)))
        if cols:
            suggestions.append(
                IndexSuggestion(
                    table=table,
                    columns=cols,
                    reason=f"Seq Scan over ~{rows} rows filtering on {cols}",
                )
            )
    return suggestions
