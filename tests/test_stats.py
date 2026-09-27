import math

import numpy as np

from keeta_voc.stats import bootstrap_ranking, newcombe_diff, wilson


def test_wilson_known_value():
    # 8/10 at 95%: textbook Wilson interval ~ (0.490, 0.943)
    lo, hi = wilson(8, 10)
    assert math.isclose(lo, 0.4902, abs_tol=5e-4) and math.isclose(hi, 0.9433, abs_tol=5e-4)


def test_wilson_edges():
    lo, hi = wilson(0, 20)
    assert lo == 0.0 and 0 < hi < 0.2
    lo, hi = wilson(20, 20)
    assert hi == 1.0 and 0.8 < lo < 1
    assert all(math.isnan(x) for x in wilson(0, 0))


def test_bootstrap_ranking_clear_winner():
    rng = np.random.default_rng(0)
    n = 200
    X = np.column_stack([rng.random(n) < 0.6, rng.random(n) < 0.2, rng.random(n) < 0.05]).astype(float)
    out = bootstrap_ranking(X, ["a", "b", "c"], n_boot=500, seed=1)
    assert out["a"]["p_rank1"] > 0.99 and out["c"]["p_rank1"] == 0.0
    assert out["a"]["rank_ci"] == [1, 1] and out["c"]["rank_ci"] == [3, 3]
    lo, hi = out["a"]["share_ci"]
    assert lo < X[:, 0].mean() < hi


def test_bootstrap_ranking_tie_is_uncertain():
    X = np.array([[1, 0], [0, 1]] * 30, dtype=float)
    out = bootstrap_ranking(X, ["a", "b"], n_boot=500, seed=2)
    assert 0.3 < out["a"]["p_rank1"] < 0.8 and 0.3 < out["b"]["p_rank1"] < 0.8
    assert out["a"]["rank_ci"] == [1, 2]


def test_newcombe_known_value():
    # Newcombe (1998) example 1: 56/70 vs 48/80 -> difference 0.2, 95% CI (0.0524, 0.3339)
    lo, hi = newcombe_diff(56, 70, 48, 80)
    assert math.isclose(lo, 0.0524, abs_tol=5e-4) and math.isclose(hi, 0.3339, abs_tol=5e-4)
    lo, hi = newcombe_diff(10, 20, 10, 20)
    assert lo < 0 < hi and math.isclose(lo, -hi)
