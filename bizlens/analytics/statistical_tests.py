"""Statistical significance testing for cohort and funnel comparisons.

The BI layer is descriptive, but BizLens adds rigour on top: differences
between cohorts are *tested*, not just displayed, and multiple comparisons are
corrected so we don't chase false positives across a 12-cohort grid.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats


@dataclass
class ProportionTestResult:
    """Result of a two-proportion comparison."""

    rate_a: float
    rate_b: float
    absolute_diff: float
    relative_lift: float
    chi2: float
    p_value: float
    significant: bool


def two_proportion_chi_square(
    conv_a: int, n_a: int, conv_b: int, n_b: int, alpha: float = 0.05
) -> ProportionTestResult:
    """Chi-squared test comparing two conversion/retention rates.

    Parameters
    ----------
    conv_a, n_a : successes and total for group A.
    conv_b, n_b : successes and total for group B.
    alpha : significance level.
    """
    if n_a == 0 or n_b == 0:
        raise ValueError("group sizes must be positive")

    rate_a = conv_a / n_a
    rate_b = conv_b / n_b
    # 2x2 contingency table: [[success, failure], ...]
    table = np.array([[conv_a, n_a - conv_a], [conv_b, n_b - conv_b]])
    chi2, p_value, _, _ = stats.chi2_contingency(table, correction=True)

    return ProportionTestResult(
        rate_a=rate_a,
        rate_b=rate_b,
        absolute_diff=rate_b - rate_a,
        relative_lift=(rate_b - rate_a) / rate_a if rate_a else float("nan"),
        chi2=float(chi2),
        p_value=float(p_value),
        significant=bool(p_value < alpha),
    )


def bonferroni_correction(
    p_values: list[float], alpha: float = 0.05
) -> tuple[list[bool], float]:
    """Apply Bonferroni correction to a family of p-values.

    Returns a list of reject/accept decisions and the corrected threshold.
    Conservative - guarantees family-wise error-rate control, which is the
    right default when comparing many cohorts against a baseline.
    """
    if not p_values:
        return [], alpha
    corrected_alpha = alpha / len(p_values)
    return [p < corrected_alpha for p in p_values], corrected_alpha


def benjamini_hochberg(
    p_values: list[float], alpha: float = 0.05
) -> list[bool]:
    """Benjamini-Hochberg FDR correction - more power than Bonferroni when
    testing many metrics. Returns reject/accept per hypothesis in input order.
    """
    n = len(p_values)
    if n == 0:
        return []
    order = np.argsort(p_values)
    ranked = np.array(p_values)[order]
    thresholds = (np.arange(1, n + 1) / n) * alpha
    passed = ranked <= thresholds
    # Largest k that passes; everything ranked below it is rejected too.
    if not passed.any():
        return [False] * n
    k_max = np.max(np.where(passed))
    decisions = np.zeros(n, dtype=bool)
    decisions[order[: k_max + 1]] = True
    return decisions.tolist()
