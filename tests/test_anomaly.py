import numpy as np

from bizlens.analytics.anomaly import WelfordDetector, scan_series


def test_welford_matches_numpy_mean_variance():
    data = [4.0, 8.0, 15.0, 16.0, 23.0, 42.0]
    d = WelfordDetector()
    for x in data:
        d.update(x)
    assert d.mean == np.mean(data)
    # Welford's sample variance (ddof=1) vs numpy.
    assert np.isclose(d.variance, np.var(data, ddof=1))


def test_scan_series_flags_injected_spike():
    rng = np.random.default_rng(0)
    series = list(rng.normal(100, 5, 50))
    series[30] = 300.0  # obvious anomaly
    anomalies = scan_series(series, sigma=2.5)
    assert 30 in anomalies


def test_no_anomaly_during_warmup():
    d = WelfordDetector(warmup=5)
    for x in [1.0, 1.0, 1.0]:
        assert not d.is_anomaly(x)
        d.update(x)


def test_flat_series_has_no_anomalies():
    assert scan_series([5.0] * 20) == []
