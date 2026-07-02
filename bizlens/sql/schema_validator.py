"""Schema validation for source tables.

Guards the ETL and reporting pipelines: a table whose columns or types have
drifted is caught before any analytics run on it.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

# Expected schema for the seeded Brazilian Olist dataset (subset used by BizLens).
EXPECTED_SCHEMAS: dict[str, dict[str, str]] = {
    "users": {
        "user_id": "object",
        "signup_date": "datetime64[ns]",
        "channel": "object",
        "country": "object",
        "segment": "object",
    },
    "events": {
        "user_id": "object",
        "event_date": "datetime64[ns]",
        "event_name": "object",
    },
    "orders": {
        "order_id": "object",
        "user_id": "object",
        "order_date": "datetime64[ns]",
        "amount": "float64",
    },
}


@dataclass
class SchemaReport:
    table: str
    ok: bool
    missing_columns: list[str] = field(default_factory=list)
    type_mismatches: dict[str, tuple[str, str]] = field(default_factory=dict)


def _dtype_category(dtype: str) -> str:
    """Bucket a dtype string into a coarse category.

    We validate the *kind* of a column (text / datetime / float / int / bool),
    not the exact backing dtype, so equivalent representations (``object`` vs
    ``str``, ``datetime64[ns]`` vs ``datetime64[us]``) don't trip the check.
    """
    d = dtype.lower()
    if d.startswith("datetime"):
        return "datetime"
    if d.startswith("float"):
        return "float"
    if d.startswith(("int", "uint")):
        return "int"
    if d.startswith("bool"):
        return "bool"
    if d.startswith(("object", "str", "string")):
        return "text"
    return d


def validate_schema(table: str, df: pd.DataFrame) -> SchemaReport:
    """Validate ``df`` against the expected schema for ``table``."""
    expected = EXPECTED_SCHEMAS.get(table)
    if expected is None:
        return SchemaReport(table=table, ok=True)  # unknown table -> no contract

    missing = [c for c in expected if c not in df.columns]
    mismatches: dict[str, tuple[str, str]] = {}
    for col, exp_type in expected.items():
        if col in df.columns:
            actual = str(df[col].dtype)
            if _dtype_category(exp_type) != _dtype_category(actual):
                mismatches[col] = (exp_type, actual)

    return SchemaReport(
        table=table,
        ok=not missing and not mismatches,
        missing_columns=missing,
        type_mismatches=mismatches,
    )
