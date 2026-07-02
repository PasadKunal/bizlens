from bizlens.dashboard.nl_to_sql import match_query
from bizlens.reporting.insight_generator import MetricDelta, generate_insight


def test_nl_to_sql_matches_country_query():
    match = match_query("show me weekly active users by country")
    assert match is not None
    assert match.query_name == "wau_by_country"
    assert "country" in match.sql.lower()


def test_nl_to_sql_matches_revenue():
    match = match_query("daily revenue for the last quarter")
    assert match is not None
    assert "revenue" in match.sql.lower()


def test_nl_to_sql_empty_question():
    assert match_query("") is None


def test_insight_template_fallback_without_openai():
    # No OPENAI_API_KEY in CI -> deterministic template path.
    deltas = [
        MetricDelta("Revenue", current=88.0, previous=100.0),
        MetricDelta("DAU", current=4820.0, previous=4700.0),
    ]
    summary = generate_insight(deltas, anomalies=["Revenue spike on 2024-03-02"])
    assert "Revenue" in summary
    assert "%" in summary
