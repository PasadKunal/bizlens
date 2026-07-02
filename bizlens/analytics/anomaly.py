"""Streaming anomaly detection using Welford's online algorithm.

Welford maintains a running mean and variance in O(1) memory per metric — no
need to store the full time series. A new observation is flagged when it lands
more than ``sigma`` standard deviations from the running mean.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class WelfordDetector:
    """Online mean/variance tracker with sigma-threshold anomaly flagging.

    Parameters
    ----------
    sigma : number of standard deviations beyond which a point is anomalous.
    warmup : minimum observations before flagging (variance is unstable early).
    """

    sigma: float = 2.5
    warmup: int = 5
    count: int = 0
    mean: float = 0.0
    _m2: float = field(default=0.0, repr=False)

    @property
    def variance(self) -> float:
        # Sample variance (ddof=1) — the unbiased estimator used for z-scores.
        return self._m2 / (self.count - 1) if self.count > 1 else 0.0

    @property
    def std(self) -> float:
        return math.sqrt(self.variance)

    def update(self, value: float) -> None:
        """Incorporate a new observation into the running statistics."""
        self.count += 1
        delta = value - self.mean
        self.mean += delta / self.count
        delta2 = value - self.mean
        self._m2 += delta * delta2

    def z_score(self, value: float) -> float:
        if self.std == 0:
            return 0.0
        return (value - self.mean) / self.std

    def is_anomaly(self, value: float) -> bool:
        """Return True if ``value`` is anomalous vs. current statistics.

        Does not update state — call :meth:`update` separately once the point
        is accepted into the baseline.
        """
        if self.count < self.warmup or self.std == 0:
            return False
        return abs(self.z_score(value)) > self.sigma


def scan_series(values: list[float], sigma: float = 2.5, warmup: int = 5) -> list[int]:
    """Return the indices of anomalous points in ``values``.

    Each point is tested against the baseline built from all *prior* points,
    then folded into the baseline — mirroring how a live metric stream behaves.
    """
    detector = WelfordDetector(sigma=sigma, warmup=warmup)
    anomalies: list[int] = []
    for i, v in enumerate(values):
        if detector.is_anomaly(v):
            anomalies.append(i)
        detector.update(v)
    return anomalies
