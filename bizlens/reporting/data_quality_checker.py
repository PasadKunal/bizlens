"""Data-quality gate that runs before any report is generated.

The worst outcome in analytics is a clean-looking report built on broken data.
Every check here must pass before a digest goes out; a failure blocks the
report and raises an alert.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class QualityCheck:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class QualityReport:
    table: str
    checks: list[QualityCheck] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def pass_rate(self) -> float:
        return sum(c.passed for c in self.checks) / len(self.checks) if self.checks else 1.0


def check_row_count(df: pd.DataFrame, min_rows: int, max_rows: int | None = None) -> QualityCheck:
    n = len(df)
    ok = n >= min_rows and (max_rows is None or n <= max_rows)
    return QualityCheck("row_count", ok, f"{n} rows (expected >= {min_rows})")


def check_no_nulls(df: pd.DataFrame, key_columns: list[str]) -> QualityCheck:
    offenders = {c: int(df[c].isna().sum()) for c in key_columns if c in df.columns}
    bad = {c: n for c, n in offenders.items() if n > 0}
    return QualityCheck("no_null_keys", not bad, f"nulls in key cols: {bad}" if bad else "ok")


def check_value_bounds(
    df: pd.DataFrame, column: str, lower: float, upper: float
) -> QualityCheck:
    if column not in df.columns:
        return QualityCheck(f"bounds:{column}", False, "column missing")
    out_of_bounds = int(((df[column] < lower) | (df[column] > upper)).sum())
    return QualityCheck(
        f"bounds:{column}", out_of_bounds == 0,
        f"{out_of_bounds} rows outside [{lower}, {upper}]",
    )


def check_no_spike(series: pd.Series, max_ratio: float = 10.0) -> QualityCheck:
    """Flag a >``max_ratio``x jump vs. the trailing median (logging-error signal)."""
    if len(series) < 2:
        return QualityCheck("no_spike", True, "insufficient history")
    baseline = series[:-1].median()
    latest = series.iloc[-1]
    ratio = latest / baseline if baseline else float("inf")
    return QualityCheck("no_spike", ratio <= max_ratio, f"latest/median = {ratio:.2f}")


def run_standard_checks(
    table: str, df: pd.DataFrame, key_columns: list[str], min_rows: int = 1
) -> QualityReport:
    """Run the default battery of checks for a source table."""
    return QualityReport(
        table=table,
        checks=[
            check_row_count(df, min_rows=min_rows),
            check_no_nulls(df, key_columns),
        ],
    )
