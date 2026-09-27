"""Interval estimates for shares and for the pain-point ranking."""
from __future__ import annotations

import math

import numpy as np


def wilson(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion k/n."""
    if n <= 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))


def bootstrap_ranking(X: np.ndarray, names: list[str], n_boot: int = 2000, seed: int = 0) -> dict:
    """X: (n_reviews x n_issues) 0/1 matrix of issue mentions among negative reviews.

    Resample reviews with replacement; per resample compute each issue's share and its rank
    (1 = highest; ties share the best rank). Returns, per issue, the percentile CI of the share,
    the probability of being ranked first, and the 95% interval of its rank.
    """
    n = X.shape[0]
    if n == 0:
        return {}
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(n_boot, n))
    shares = X[idx].mean(axis=1)  # (n_boot, n_issues)
    # rank with ties -> best rank: 1 + number of issues strictly larger
    ranks = 1 + (shares[:, None, :] > shares[:, :, None]).sum(axis=2)
    out = {}
    for j, name in enumerate(names):
        out[name] = {
            "share_ci": [float(np.quantile(shares[:, j], 0.025)), float(np.quantile(shares[:, j], 0.975))],
            "p_rank1": float((ranks[:, j] == 1).mean()),
            "rank_ci": [int(np.quantile(ranks[:, j], 0.025, method="lower")),
                        int(np.quantile(ranks[:, j], 0.975, method="higher"))],
        }
    return out
