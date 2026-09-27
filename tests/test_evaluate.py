import math

import numpy as np

from keeta_voc.evaluate import cohen_kappa, evaluate, exact_match, macro_f1, micro_f1, paired_diff, prf, to_matrix
from keeta_voc.taxonomy import label_names


def test_prf_hand_computed():
    y = np.array([1, 1, 1, 0, 0, 0])
    p = np.array([1, 1, 0, 1, 0, 0])
    prec, rec, f1, tp, fp, fn = prf(y, p)
    assert (tp, fp, fn) == (2, 1, 1)
    assert math.isclose(prec, 2 / 3) and math.isclose(rec, 2 / 3) and math.isclose(f1, 2 / 3)


def test_prf_undefined_is_nan_not_zero():
    prec, rec, f1, *_ = prf(np.zeros(4, int), np.zeros(4, int))
    assert math.isnan(prec) and math.isnan(rec) and math.isnan(f1)


def test_kappa_hand_computed():
    # po = 0.75, pe = 0.5*0.25 + 0.5*0.75 = 0.5  ->  kappa = 0.5
    assert math.isclose(cohen_kappa(np.array([1, 1, 0, 0]), np.array([1, 0, 0, 0])), 0.5)
    assert math.isclose(cohen_kappa(np.array([1, 0, 1, 0]), np.array([1, 0, 1, 0])), 1.0)
    assert math.isclose(cohen_kappa(np.array([1, 0, 1, 0]), np.array([0, 1, 0, 1])), -1.0)
    assert math.isnan(cohen_kappa(np.zeros(3, int), np.zeros(3, int)))


def test_to_matrix_handles_invalid_and_other():
    names = label_names()
    m = to_matrix(["a", "b", "c"], {"a": ["other"], "b": None, "c": ["delivery_time", "app_ux"]}, names)
    assert m[0, names.index("other")] == 1 and m[0].sum() == 1
    assert m[1].sum() == 0                       # invalid prediction -> predicts nothing
    assert m[2, names.index("delivery_time")] == 1 and m[2, names.index("app_ux")] == 1


def test_overall_scores():
    Y = np.array([[1, 0], [0, 1], [1, 1]])
    P = np.array([[1, 0], [0, 0], [1, 1]])
    assert math.isclose(micro_f1(Y, P), 2 * 3 / (2 * 3 + 0 + 1))
    assert math.isclose(macro_f1(Y, P), (1.0 + 2 / 3) / 2)
    assert math.isclose(exact_match(Y, P), 2 / 3)


def test_evaluate_bootstrap_is_seeded_and_brackets_point():
    rng = np.random.default_rng(3)
    names = label_names()
    Y = (rng.random((120, len(names))) < 0.3).astype(int)
    P = np.where(rng.random(Y.shape) < 0.8, Y, 1 - Y)
    a = evaluate(Y, P, names, n_boot=300, seed=0)
    b = evaluate(Y, P, names, n_boot=300, seed=0)
    assert a == b
    for name in names:
        r = a["per_label"][name]
        lo, hi = r["f1_ci"]
        assert lo <= r["f1"] <= hi
        assert r["support"] == int(Y[:, names.index(name)].sum())
    assert a["overall"]["micro_f1_ci"][0] <= a["overall"]["micro_f1"] <= a["overall"]["micro_f1_ci"][1]


def test_paired_diff_sign():
    rng = np.random.default_rng(5)
    names = label_names()
    Y = (rng.random((150, len(names))) < 0.3).astype(int)
    good = Y.copy()
    bad = np.where(rng.random(Y.shape) < 0.6, Y, 1 - Y)
    d = paired_diff(Y, bad, good, n_boot=300)
    assert d["micro_f1"]["diff"] > 0 and d["micro_f1"]["ci"][0] > 0
