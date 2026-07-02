import pytest

from bizlens.analytics.statistical_tests import (
    benjamini_hochberg,
    bonferroni_correction,
    two_proportion_chi_square,
)


def test_chi_square_detects_real_difference():
    # 50% vs 40% conversion on large samples -> clearly significant.
    res = two_proportion_chi_square(500, 1000, 400, 1000)
    assert res.significant
    assert res.rate_a == pytest.approx(0.5)
    assert res.rate_b == pytest.approx(0.4)
    assert res.relative_lift == pytest.approx(-0.2)


def test_chi_square_no_difference_not_significant():
    res = two_proportion_chi_square(500, 1000, 505, 1000)
    assert not res.significant


def test_chi_square_rejects_zero_group():
    with pytest.raises(ValueError):
        two_proportion_chi_square(1, 0, 1, 10)


def test_bonferroni_threshold_and_decisions():
    decisions, corrected = bonferroni_correction([0.001, 0.02, 0.04], alpha=0.05)
    assert corrected == pytest.approx(0.05 / 3)
    assert decisions == [True, False, False]


def test_bonferroni_empty():
    assert bonferroni_correction([]) == ([], 0.05)


def test_benjamini_hochberg_more_powerful_than_bonferroni():
    p = [0.001, 0.008, 0.02, 0.04, 0.9]
    bh = benjamini_hochberg(p, alpha=0.05)
    bonf, _ = bonferroni_correction(p, alpha=0.05)
    # BH rejects at least as many as Bonferroni.
    assert sum(bh) >= sum(bonf)
    assert bh[0] is True and bh[-1] is False
