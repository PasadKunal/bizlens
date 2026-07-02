"""End-to-end warehouse tests against a live Postgres.

Auto-skipped when no database is reachable (e.g. CI without a service
container), so the default `pytest` run stays hermetic. To run them locally:

    docker compose -f bizlens/infra/docker-compose.yml up -d postgres redis
    python scripts/generate_sample_data.py && python -m bizlens.sql.etl_pipeline
    pytest tests/test_integration_warehouse.py
"""
import pytest

from bizlens.db import ping, sandboxed_query

pytestmark = pytest.mark.skipif(not ping(), reason="no database reachable")


def test_retention_matrix_bounded():
    from bizlens import warehouse

    m = warehouse.retention_matrix()
    assert not m.empty
    # No cell may exceed 100% retention.
    assert m.values.max() <= 1.0001


def test_funnel_is_monotonic():
    from bizlens import warehouse

    steps = warehouse.funnel()
    counts = [s.users for s in steps]
    assert counts == sorted(counts, reverse=True)
    assert all(0.0 <= s.conversion_from_prev <= 1.0001 for s in steps)


def test_kpi_cards_present():
    from bizlens import warehouse

    names = {c.name for c in warehouse.compute_kpi_cards()}
    assert {"DAU", "WAU", "MAU", "Revenue (30d)", "Churn rate"} <= names


def test_sandbox_rejects_non_select():
    with pytest.raises(ValueError):
        sandboxed_query("DELETE FROM users")


def test_sandbox_row_cap():
    # The wrapper LIMIT must cap results regardless of the inner query.
    df = sandboxed_query("SELECT * FROM events", row_cap=5)
    assert len(df) <= 5
