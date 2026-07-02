import pandas as pd

from bizlens.analytics.cohort_analysis import (
    churn_signal_cohorts,
    retention_matrix_from_events,
)


def _fixture():
    signups = pd.DataFrame(
        {"user_id": ["a", "b", "c"], "signup_date": ["2024-01-01"] * 3}
    )
    events = pd.DataFrame(
        {
            "user_id": ["a", "b", "c", "a", "b", "a"],
            "event_date": [
                "2024-01-01", "2024-01-02", "2024-01-03",  # week 0: all three
                "2024-01-08", "2024-01-09",                # week 1: a, b
                "2024-01-15",                              # week 2: a
            ],
        }
    )
    return events, signups


def test_retention_matrix_fractions():
    events, signups = _fixture()
    matrix = retention_matrix_from_events(events, signups, max_weeks=4)
    # Week 0 = 100% by construction.
    assert matrix.iloc[0][0] == 1.0
    # Week 1: 2 of 3 users returned.
    assert matrix.iloc[0][1] == 2 / 3
    # Week 2: 1 of 3.
    assert matrix.iloc[0][2] == 1 / 3


def test_churn_signal_flags_low_cohort():
    matrix = pd.DataFrame(
        {4: [0.5, 0.52, 0.48, 0.1]},
        index=pd.to_datetime(["2024-01-01", "2024-01-08", "2024-01-15", "2024-01-22"]),
    )
    flagged = churn_signal_cohorts(matrix, week=4, sigma=1.0)
    assert pd.Timestamp("2024-01-22") in flagged
