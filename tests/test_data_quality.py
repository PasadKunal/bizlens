import pandas as pd

from bizlens.reporting.data_quality_checker import (
    check_no_nulls,
    check_no_spike,
    check_row_count,
    run_standard_checks,
)


def test_row_count_check():
    df = pd.DataFrame({"a": range(10)})
    assert check_row_count(df, min_rows=5).passed
    assert not check_row_count(df, min_rows=20).passed


def test_null_key_check():
    df = pd.DataFrame({"user_id": [1, None, 3]})
    assert not check_no_nulls(df, ["user_id"]).passed
    df2 = pd.DataFrame({"user_id": [1, 2, 3]})
    assert check_no_nulls(df2, ["user_id"]).passed


def test_spike_check():
    steady = pd.Series([100, 102, 98, 101, 99])
    assert check_no_spike(steady).passed
    spiked = pd.Series([100, 102, 98, 101, 2000])
    assert not check_no_spike(spiked).passed


def test_standard_report_pass_rate():
    df = pd.DataFrame({"user_id": [1, 2, 3]})
    report = run_standard_checks("users", df, key_columns=["user_id"])
    assert report.passed
    assert report.pass_rate == 1.0
