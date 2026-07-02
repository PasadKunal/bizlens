import pytest

from bizlens.analytics.funnel_analysis import compare_funnels, compute_funnel


def test_compute_funnel_dropoff():
    steps = compute_funnel([("visit", 1000), ("cart", 400), ("purchase", 100)])
    assert steps[0].conversion_from_start == 1.0
    assert steps[1].conversion_from_prev == pytest.approx(0.4)
    assert steps[1].dropoff_from_prev == pytest.approx(0.6)
    assert steps[2].conversion_from_start == pytest.approx(0.1)


def test_compute_funnel_empty():
    assert compute_funnel([]) == []


def test_compare_funnels_flags_significant_gap():
    seg_a = [("visit", 5000), ("cart", 2500)]   # 50%
    seg_b = [("visit", 5000), ("cart", 1500)]   # 30%
    res = compare_funnels(seg_a, seg_b)
    assert res["cart"].significant
