"""Label quality against the reference set: per-label P/R/F1, Cohen's kappa, bootstrap CIs."""
from __future__ import annotations

import numpy as np

from .taxonomy import label_names


def to_matrix(keys: list[str], labels: dict[str, list[str] | None], names: tuple[str, ...]) -> np.ndarray:
    """Binary matrix (n_reviews x n_labels). A missing/invalid prediction (None) is an all-zero row."""
    idx = {n: j for j, n in enumerate(names)}
    m = np.zeros((len(keys), len(names)), dtype=np.int8)
    for i, k in enumerate(keys):
        for lab in labels.get(k) or []:
            m[i, idx[lab]] = 1
    return m


def prf(y: np.ndarray, p: np.ndarray) -> tuple[float, float, float, int, int, int]:
    """Precision, recall, F1 for one binary column (0/0 is reported as NaN, not 0 or 1)."""
    tp = int(((y == 1) & (p == 1)).sum())
    fp = int(((y == 0) & (p == 1)).sum())
    fn = int(((y == 1) & (p == 0)).sum())
    prec = tp / (tp + fp) if tp + fp else float("nan")
    rec = tp / (tp + fn) if tp + fn else float("nan")
    f1 = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else float("nan")
    return prec, rec, f1, tp, fp, fn


def cohen_kappa(y: np.ndarray, p: np.ndarray) -> float:
    """Cohen's kappa for two binary raters. NaN when chance agreement is 1 (both constant, equal)."""
    n = len(y)
    if n == 0:
        return float("nan")
    po = float((y == p).mean())
    py1, pp1 = float(y.mean()), float(p.mean())
    pe = py1 * pp1 + (1 - py1) * (1 - pp1)
    if pe == 1.0:
        return float("nan")
    return (po - pe) / (1 - pe)


def micro_f1(Y: np.ndarray, P: np.ndarray) -> float:
    tp = int(((Y == 1) & (P == 1)).sum())
    fp = int(((Y == 0) & (P == 1)).sum())
    fn = int(((Y == 1) & (P == 0)).sum())
    return 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else float("nan")


def macro_f1(Y: np.ndarray, P: np.ndarray) -> float:
    vals = [prf(Y[:, j], P[:, j])[2] for j in range(Y.shape[1])]
    vals = [v for v in vals if not np.isnan(v)]
    return float(np.mean(vals)) if vals else float("nan")


def exact_match(Y: np.ndarray, P: np.ndarray) -> float:
    return float((Y == P).all(axis=1).mean())


def _ci(samples: list[float], alpha: float = 0.05) -> list[float | None]:
    arr = np.array([s for s in samples if not np.isnan(s)])
    if len(arr) == 0:
        return [None, None]
    return [float(np.quantile(arr, alpha / 2)), float(np.quantile(arr, 1 - alpha / 2))]


def evaluate(Y: np.ndarray, P: np.ndarray, names: tuple[str, ...], n_boot: int = 2000, seed: int = 0) -> dict:
    """Point estimates + percentile bootstrap CIs (resampling reviews)."""
    rng = np.random.default_rng(seed)
    n = Y.shape[0]
    boots = rng.integers(0, n, size=(n_boot, n))
    per_label = {}
    for j, name in enumerate(names):
        y, p = Y[:, j], P[:, j]
        prec, rec, f1, tp, fp, fn = prf(y, p)
        kap = cohen_kappa(y, p)
        bs = {"precision": [], "recall": [], "f1": [], "kappa": []}
        for b in boots:
            pb = prf(y[b], p[b])
            bs["precision"].append(pb[0])
            bs["recall"].append(pb[1])
            bs["f1"].append(pb[2])
            bs["kappa"].append(cohen_kappa(y[b], p[b]))
        per_label[name] = {
            "support": int(y.sum()), "predicted": int(p.sum()), "tp": tp, "fp": fp, "fn": fn,
            "precision": _nan_to_none(prec), "recall": _nan_to_none(rec), "f1": _nan_to_none(f1),
            "kappa": _nan_to_none(kap),
            "precision_ci": _ci(bs["precision"]), "recall_ci": _ci(bs["recall"]), "f1_ci": _ci(bs["f1"]),
            "kappa_ci": _ci(bs["kappa"]),
        }
    overall = {"micro_f1": micro_f1(Y, P), "macro_f1": macro_f1(Y, P), "exact_match": exact_match(Y, P)}
    ob = {k: [] for k in overall}
    for b in boots:
        ob["micro_f1"].append(micro_f1(Y[b], P[b]))
        ob["macro_f1"].append(macro_f1(Y[b], P[b]))
        ob["exact_match"].append(exact_match(Y[b], P[b]))
    overall = {k: _nan_to_none(v) for k, v in overall.items()}
    overall.update({f"{k}_ci": _ci(v) for k, v in ob.items()})
    return {"n": int(n), "per_label": per_label, "overall": overall}


def paired_diff(Y: np.ndarray, A: np.ndarray, B: np.ndarray, n_boot: int = 2000, seed: int = 0) -> dict:
    """Bootstrap CI of per-label F1(B) - F1(A) and micro-F1(B) - micro-F1(A) on the same resamples."""
    rng = np.random.default_rng(seed + 1)
    n = Y.shape[0]
    boots = rng.integers(0, n, size=(n_boot, n))
    out = {}
    for j, name in enumerate(label_names()):
        d = [prf(Y[b, j], B[b, j])[2] - prf(Y[b, j], A[b, j])[2] for b in boots]
        point = prf(Y[:, j], B[:, j])[2] - prf(Y[:, j], A[:, j])[2]
        out[name] = {"diff": _nan_to_none(point), "ci": _ci(d)}
    d = [micro_f1(Y[b], B[b]) - micro_f1(Y[b], A[b]) for b in boots]
    out["micro_f1"] = {"diff": micro_f1(Y, B) - micro_f1(Y, A), "ci": _ci(d)}
    return out


def _nan_to_none(x):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else float(x)
