"""Pre-built, validated analytical queries.

These are the templates the NL-to-SQL layer matches against and the dashboard
calls directly. Keeping them here (rather than inline) means every query is
reviewed, indexed, and safe to run under the read-only analyst role.
"""
from __future__ import annotations

QUERY_LIBRARY: dict[str, dict[str, str]] = {
    "weekly_active_users": {
        "description": "Weekly active users (WAU) over the trailing 12 weeks.",
        "sql": """
            SELECT date_trunc('week', event_date) AS week,
                   COUNT(DISTINCT user_id) AS wau
            FROM events
            WHERE event_date >= CURRENT_DATE - INTERVAL '84 days'
            GROUP BY 1 ORDER BY 1;
        """,
    },
    "wau_by_country": {
        "description": "Weekly active users by country for the last 3 months.",
        "sql": """
            SELECT date_trunc('week', e.event_date) AS week,
                   u.country,
                   COUNT(DISTINCT e.user_id) AS wau
            FROM events e
            JOIN users u ON u.user_id = e.user_id
            WHERE e.event_date >= CURRENT_DATE - INTERVAL '90 days'
            GROUP BY 1, 2 ORDER BY 1, 2;
        """,
    },
    "daily_revenue": {
        "description": "Daily total revenue over the last 90 days.",
        "sql": """
            SELECT date_trunc('day', order_date) AS day,
                   SUM(amount) AS revenue
            FROM orders
            WHERE order_date >= CURRENT_DATE - INTERVAL '90 days'
            GROUP BY 1 ORDER BY 1;
        """,
    },
    "revenue_by_segment": {
        "description": "Revenue split by customer segment for the last 30 days.",
        "sql": """
            SELECT u.segment,
                   SUM(o.amount) AS revenue,
                   COUNT(DISTINCT o.user_id) AS paying_users
            FROM orders o
            JOIN users u ON u.user_id = o.user_id
            WHERE o.order_date >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY 1 ORDER BY 2 DESC;
        """,
    },
    "new_signups_by_channel": {
        "description": "New signups per week broken down by acquisition channel.",
        "sql": """
            SELECT date_trunc('week', signup_date) AS week,
                   channel,
                   COUNT(*) AS signups
            FROM users
            WHERE signup_date >= CURRENT_DATE - INTERVAL '84 days'
            GROUP BY 1, 2 ORDER BY 1, 2;
        """,
    },
}


def list_queries() -> list[dict[str, str]]:
    """Return metadata for every query in the library."""
    return [{"name": k, "description": v["description"]} for k, v in QUERY_LIBRARY.items()]


def get_query(name: str) -> str:
    """Return the SQL for ``name`` or raise KeyError."""
    return QUERY_LIBRARY[name]["sql"].strip()
